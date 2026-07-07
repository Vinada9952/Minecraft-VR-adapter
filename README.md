# Minecraft VR adapter

Un adaptateur VR local pour Windows qui capture l'écran du PC, l'envoie en flux vers un iPhone et utilise le gyroscope du téléphone pour déplacer la souris.

## Fonctionnalités

- Capture en continu l'écran Windows via `mss`.
- Envoie des images JPEG en binaire au client iPhone avec Socket.IO.
- Affiche le flux en double (œil gauche / œil droit) pour un rendu VR stéréoscopique.
- Reçoit les données du gyroscope du téléphone et convertit les rotations en mouvements de souris relatifs.
- Permet la calibration de la sensibilité et du rendu VR depuis un panneau de configuration PC.

## Prérequis

- Windows 10 / 11
- Python 3.8+ installé
- iPhone et PC sur le même réseau local
- Certificat HTTPS recommandé pour iOS (obligatoire pour accéder au gyroscope depuis Safari)

## Installation

1. Ouvre une console dans le dossier du projet.
2. Installe les dépendances Python :

```powershell
pip install flask flask-socketio mss opencv-python numpy pywin32
```

## Configuration

### Certificat HTTPS (recommandé)

Le projet tente de charger `CERT_FILE` et `KEY_FILE` depuis le dossier du projet. Si ces fichiers existent, le serveur démarre en HTTPS.

Par défaut, `server.py` cherche des fichiers comme :

- `192.168.0.120+2.pem`
- `192.168.0.120+2-key.pem`

Pour générer un certificat local sur Windows, tu peux utiliser `mkcert` :

```powershell
mkcert -install
mkcert 192.168.0.120 localhost 127.0.0.1
```

Puis place les fichiers `.pem` générés à côté de `server.py`.

> Remarque : si le certificat n'est pas trouvé, le serveur démarre en HTTP,
> mais le gyroscope iPhone ne fonctionnera pas depuis Safari.

### Paramètres de capture

Dans `server.py`, tu peux ajuster :

- `MONITOR_INDEX` : index de l'écran à capturer (par défaut `3`).
- `TARGET_WIDTH` : largeur de l'image envoyée au client.
- `FPS_TARGET` : cadence de capture.
- `MOUSE_SENSITIVITY` : sensibilité globale de la conversion gyroscope -> souris.
- `HOST` / `PORT` : adresse et port du serveur.

## Utilisation

1. Lance le serveur :

```powershell
python server.py
```

2. Sur l'iPhone, ouvre Safari et visite :

- `https://<IP_PC>:5000/` si HTTPS est disponible,
- sinon `http://<IP_PC>:5000/`.

3. Appuie sur le bouton Démarrer dans la page Web.
4. Le flux vidéo VR apparaît et le gyroscope commence à envoyer les rotations au serveur.
5. Ajuste la sensibilité depuis le curseur du téléphone ou via la page de réglages PC.

## Pages disponibles

- `http://<IP_PC>:5000/` : page client iPhone (`page.html`).
- `http://<IP_PC>:5000/settings` : panneau de configuration PC via `settings.html`.

## Page de réglages PC

Ouvre `settings.html` sur le PC ou visite `/settings` pour modifier :

- `mouseSensitivityX` : sensibilité horizontale.
- `mouseSensitivityY` : sensibilité verticale.
- `warpTL`, `warpTR`, `warpBL`, `warpBR` : déformation des coins de l'image.
- `eyeGap` : espacement entre les deux images.
- `eyeZoom` : zoom appliqué à chaque œil.

Ces réglages sont envoyés directement au client VR connecté et appliqués en temps réel.

## Conseils

- Vérifie que le pare-feu Windows autorise Python et le port `5000`.
- Pour un rendu plein écran sur iPhone, ajoute la page à l'écran d'accueil et lance-la depuis l'icône.
- Si l'écran est inversé ou mal cadré, ajuste `MONITOR_INDEX` et les paramètres de déformation.
- Si le flux est lent, démarre le serveur en HTTPS uniquement si le certificat est présent ; sinon l'envoi d'images reste possible en HTTP sans gyroscope.

## Limites

- Projet conçu pour une utilisation locale et expérimentale.
- Le gyroscope iOS nécessite HTTPS et le chargement depuis Safari.
- Le projet ne gère pas encore de synchronisation audio.
- La capture fonctionne sur Windows uniquement.

## Fichiers principaux

- `server.py` : serveur Flask + Socket.IO et conversion gyroscope -> souris.
- `page.html` : interface client iPhone pour le flux VR.
- `settings.html` : interface de réglage sur le PC.

## Licence

Consulte `LICENCE.md` pour les détails de licence.
