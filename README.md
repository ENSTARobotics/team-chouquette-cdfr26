# ENSTA Gros Robot

Logiciel de pilotage Raspberry Pi + ESP32 pour le gros robot Eurobot.

Le dépôt contient :

- `src/robot_control/` : version principale du contrôle robot ;
- `hardware/esp32/` : firmware Arduino de l’ESP32 ;
- `tools/vision/` : essais caméra, ArUco et projection du plateau ;
- `examples/serial/` : scripts de diagnostic série ;
- `tests/` : mocks série et éléments de test ;
- `archive/` : anciennes variantes conservées pour traçabilité, ignorées par Git.

## Installation Raspberry Pi

```bash
git clone <URL_DU_DEPOT>
cd ensta-gros-robot
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Le port série par défaut est `/dev/serial0` à `115200 bauds`. Vérifier les droits
de l’utilisateur et la configuration UART de la Raspberry Pi avant tout essai.

## Lancer le contrôle principal

```bash
PYTHONPATH=src python3 -m robot_control.main
```

Le lancement nécessite l’ESP32 connecté et doit être effectué après vérification
du bouton d’arrêt d’urgence. Les constantes de navigation, les angles des
servos et les broches ESP32 restent à calibrer sur le matériel réel.

## Vérifications locales

```bash
python3 -m compileall -q src tests tools examples
python3 -m unittest discover -s tests -v
```

Ces commandes vérifient le code statiquement ; elles ne remplacent pas un test
sur robot ni une validation complète du protocole série.

## Protocole série

Messages ESP32 vers Raspberry Pi :

```text
POS:<x>,<y>,<theta>
SONAR:<d1>,<d2>,<d3>,<d4>
EVT:START
EVT:READY
```

Messages Raspberry Pi vers ESP32 :

```text
MOT:<dir1>,<pwm1>,<dir2>,<pwm2>
SRV:<id>,<angle>
SRVALL:<a1>,<a2>,<a3>,<a4>,<a5>
STOP
RESET
SETPOS:<x>,<y>,<theta>
```

## État du dépôt

La version principale est issue de la variante multi-sonars de `files_2`.
Les anciennes implémentations ne sont pas supprimées : elles sont placées dans
`archive/legacy/` afin de permettre une comparaison ou une récupération.
