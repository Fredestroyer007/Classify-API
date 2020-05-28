# API pour l'application Classify

Cette repo est l'API dans un contenant Docker pour l'application Classify qui catégorise le genre musical d'un extrait audio par apprentissage profond.

L'application Classify est développé dans le cadre d'un projet d'intégration à la session d'hiver 2020 au Collège de Bois-de-Boulogne.

L'API est déployé sur [Render](https://render.com/) pour un faible coût de 7$ par mois pour faciliter le développement en raison que chaque commit dans cette repo est automatiquement appliqué au déploiement. La version finale sera déployé sur une instance [EC2 AWS](https://aws.amazon.com/ec2/) pour un gain de performance.

Basé sur l'implémentation par [Fastai](https://course.fast.ai/deployment_render.html) pour un déploiement sur [Render](https://render.com/).
