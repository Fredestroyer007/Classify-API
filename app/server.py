import aiohttp
import asyncio
import uvicorn
import librosa
import librosa.display
import matplotlib.pyplot as plt
import numpy as np
import soundfile as sf
import math

from pydub import AudioSegment
from fastai import *
from fastai.vision import *
from io import BytesIO
from starlette.applications import Starlette
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import HTMLResponse, JSONResponse
from starlette.staticfiles import StaticFiles


# INFO SI L'IDE LANCE PLEIN D'ERREUR SUR WINDOWS, C'EST NORMAL, TOUT LES IMPORTS NE SONT PAS INSTALLER SUR WINDOWS, MAIS ILS SONT INSTALLER LORS 
# DE LA COMPILATION DU CONTENANT DOCKER


# URL du modèle pickle avec un lien de téléchargement google drive
export_file_url = 'https://drive.google.com/uc?export=download&id=1n6lQ8kHnYLsE9O--3FcGSbdbjMtXvKUi'
# Nom du fichier du modèle pickle
export_file_name = 'vgg16.pkl'

# Les 8 catégories de classification du modèle
classes = ['Electronic', 'Experimental', 'Folk', 'Hip-Hop',
           'Instrumental', 'International', 'Pop', 'Rock']
# Path non-absolu (truc weird Docker)
path = Path(__file__).parent

# Création de l'objet Starlette qui gère le serveur ASGI pour permettre d'uploader depuis l'application les fichiers audios
app = Starlette()
app.add_middleware(CORSMiddleware, allow_origins=[
                   '*'], allow_headers=['X-Requested-With', 'Content-Type'])
app.mount('/static', StaticFiles(directory='app/static'))

# Méthode pour télécharger le fichier audio (tel quel de Fastai)
async def download_file(url, dest):
    if dest.exists():
        return
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            data = await response.read()
            with open(dest, 'wb') as f:
                f.write(data)

# Méthode pour initier l'inférence (tel quel de Fastai)
async def setup_learner():
    await download_file(export_file_url, path / export_file_name)
    try:
        learn = load_learner(path, export_file_name)
        return learn
    except RuntimeError as e:
        if len(e.args) > 0 and 'CPU-only machine' in e.args[0]:
            print(e)
            message = "\n\nThis model was trained with an old version of fastai and will not work in a CPU environment.\n\nPlease update the fastai library in your training environment and export your model again.\n\nSee instructions for 'Returning to work' at https://course.fast.ai."
            raise RuntimeError(message)
        else:
            raise

# Fonctionne en concurrence avec d'autres services (essentiel, il s'agit d'une serveur) (tel quel de Fastai)
loop = asyncio.get_event_loop()
tasks = [asyncio.ensure_future(setup_learner())]
learn = loop.run_until_complete(asyncio.gather(*tasks))[0]
loop.close()

# Genre la communication avec le GUI de l'API (tel quel de Fastai)
@app.route('/')
async def homepage(request):
    html_file = path / 'view' / 'index.html'
    return HTMLResponse(html_file.open().read())

# Ma méthode pour analyser le fichier audio, le conteneur Docker lance un paquet d'exception, mais tout fonctionne, 
# le traitement de fichier audio en général avec Python (dans Docker, sur un serveur, c'est encore pire) est un vrai
# cauchemar, j'ai eu besoin de 7 jours pour faire fonctionner cette fonction, Docker et audio python = cauchemar
@app.route('/analyze', methods=['POST'])
async def analyze(request):

    # en attente d'une demande
    audio_data = await request.form()
    # téléchargement du stream paquet du fichier audio
    audio_bytes = await (audio_data['file'].read())
    # reconstruction des bytes du stream (il ne s'agit pas encore d'un fichier audio, seulement d'un stream de paquet en bytes)
    audio_bytes = bytes(audio_bytes) 
    # reconstruction en un seul stream continu
    s = BytesIO(audio_bytes)  
    # reconstruction en un path (il ne s'agit pas encore d'un fichier audio, particularité en raison de Docker = cauchemar) depuis le stream de bytes
    audioObj = AudioSegment.from_file(s)
    # paramètre pour le renderer du fichier audio
    audioObj = audioObj.set_sample_width(2).set_frame_rate(16000).set_channels(1)
    # variable qui garde en mémoire la durée du "fichier audio" (il ne s'agit pas encore d'un fichier audio)
    duration = audioObj.duration_seconds
    # rendu sous forme d'un fichier audio (enfin on a un fichier audio!! *que librosa va accepter, librosa est vraiment picky)
    audioObj.export("input_audio.wav")

    # calcul d'un nombre de segment (nombre de spectrogramme) à générer
    loop_size = math.floor(duration/2)

    # met une limite sur le nombre de spectrogramme, le processus est déjà assez lent pour une seule image...
    if loop_size > 6:
        loop_size=6

    # création d'un dictionnaire pour le voting system
    voting_dict = dict()

    # loop qui génère un certain nombre de spectrogramme (dépendant de la valeur calculer loop_size)
    for i in range(1, loop_size):
        # exactement le même worflow que dans le notebook d'apprentissage profond pour générer des images identiques pour le modèle
        y, sr = librosa.load("input_audio.wav", mono=True, offset=0.1, duration=(2*i))
        spect = librosa.feature.melspectrogram(y=y, sr=sr, n_fft=512, hop_length=256, fmax=8000, n_mels=128)
        spect = librosa.power_to_db(spect, ref=np.max)
        librosa.display.specshow(spect)
        plt.axis('off')
        plt.savefig('temp.png')

        # ouverture du fichier, .predict accepte seulement une image et non un path vers une image
        img = open_image('temp.png')
        # retourne un string de la catégorie prédite et des tensors
        # TODO Utiliser les tensors pour faire un "weighted-average" pour le voting system
        prediction = learn.predict(img)[0]
    

        # Python is soo smooooothhhh
        #Façon super élégante d'incrémenter une série de valeur pour le voting system, ne génére pas des keys inutiles
        if str(prediction) in voting_dict:  #si la key est déjà présente dans le dict
            voting_dict[str(prediction)] += 1   #incrémente sa valeur de 1
        else:   #si la key n'est pas présente dans le dict
            voting_dict[str(prediction)] = 1  #crée une nouvelle key et l'initialiser avec une valeur de 1

    #retourne la key avec la valeur maximale (comme ça, on a un élégant voting system pour augmenter la précision de la prédiction)
    maximum = max(voting_dict, key=voting_dict.get)

    #Réponse de l'API sur le genre du fichier audio
    return JSONResponse({'result': str(maximum)})


if __name__ == '__main__':
    if 'serve' in sys.argv:
        uvicorn.run(app=app, host='0.0.0.0', port=5000, log_level="info")
