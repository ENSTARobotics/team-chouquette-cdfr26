/* ============================================================================
 *  EUROBOT 2026 - GROS ROBOT - CODE ESP32
 * ============================================================================
 *  Rôle de l'ESP32 :
 *   - Lire les 4 sonars (HC-SR04) -> envoyer D1..D4 à la Raspberry Pi
 *   - Lire l'odométrie (2 encodeurs) -> calculer X, Y, theta -> envoyer à la Pi
 *   - Recevoir les commandes de la Pi :
 *       * Moteurs DC (DM1/PM1, DM2/PM2)
 *       * Servos (S1..S5)
 *   - Gérer le bouton d'arrêt d'urgence + le tirette de départ
 *
 *  Protocole série (Serial2 @ 115200 bauds) - format texte ligne par ligne :
 *
 *   ESP32 -> Pi :
 *     POS:<x>,<y>,<theta>           (mm, mm, rad) toutes les 50 ms
 *     SONAR:<d1>,<d2>,<d3>,<d4>     (mm)          toutes les 100 ms
 *     EVT:START                     tirette tirée
 *     ACK:<id>                      accusé de réception d'une commande
 *
 *   Pi -> ESP32 :
 *     MOT:<dm1>,<pm1>,<dm2>,<pm2>   dm = 0/1, pm = 0..255
 *     SRV:<id>,<angle>              id = 1..5 ; angle en degrés (0..180)
 *     SRVALL:<a1>,<a2>,<a3>,<a4>,<a5>  régler tous les servos d'un coup
 *     STOP                          arrêt moteurs
 *     RESET                         remise à zéro de l'odométrie
 *     SETPOS:<x>,<y>,<theta>        forcer la position (calibration)
 *
 *  Convention servos :
 *   - S1..S4 : 4 servos avant ("barrières" qui calent les caisses sous le robot)
 *       OPEN (=0°)   : barrière levée -> le robot peut glisser sous les caisses
 *       CLOSE (=100°) : barrière baissée -> les caisses sont calées sous le robot
 *   - S5 : servo arrière (libération des caisses)
 *       CLOSE (=0°)  : barrière baissée -> les caisses restent dans le robot
 *       OPEN (=90°)  : barrière levée -> les caisses sont libérées vers l'arrière
 *
 *  À AJUSTER : les pins, les angles min/max des servos, et les constantes
 *  d'odométrie selon votre matériel.
 * ============================================================================
 */
 
#include <ESP32Servo.h>

// ============================================================================
//                       CONFIGURATION DES PINS
// ============================================================================
// --- UART vers Raspberry Pi (Serial2) ---
#define PIN_RX2        16
#define PIN_TX2        17

// --- Encodeurs roues (odométrie) ---
// Roue gauche
#define PIN_ENC_L_A    4
#define PIN_ENC_L_B    5
// Roue droite
#define PIN_ENC_R_A    18
#define PIN_ENC_R_B    19

// --- Moteurs DC (driver type L298N / BTS7960 / DRV8871) ---
#define PIN_MOT1_DIR   25
#define PIN_MOT1_PWM   26
#define PIN_MOT2_DIR   27
#define PIN_MOT2_PWM   14

// Canaux LEDC ESP32 pour PWM moteurs
#define CH_PWM_MOT1    0
#define CH_PWM_MOT2    1
#define PWM_FREQ       20000   // 20 kHz (au-dessus de l'audible)
#define PWM_RES        8       // 8 bits -> 0..255

// --- Sonars HC-SR04 ---
#define PIN_SONAR1_TRIG  32
#define PIN_SONAR1_ECHO  33
#define PIN_SONAR2_TRIG  13
#define PIN_SONAR2_ECHO  12
#define PIN_SONAR3_TRIG  15
#define PIN_SONAR3_ECHO  2
#define PIN_SONAR4_TRIG  21
#define PIN_SONAR4_ECHO  22

// --- Servos ---
#define PIN_SERVO1     23   // avant gauche extérieur
#define PIN_SERVO2     1    // avant gauche intérieur (UART0 TX libre si Serial uniquement debug)
#define PIN_SERVO3     3    // avant droit intérieur
#define PIN_SERVO4     0    // avant droit extérieur (attention strapping pin !)
#define PIN_SERVO5     29   // arrière
// NOTE : adaptez ces pins selon votre carte. Évitez les pins de strapping
// (0, 2, 5, 12, 15) si possible pour les servos.

// --- Tirette de départ et bouton d'arrêt d'urgence ---
#define PIN_TIRETTE    34   // input only (pull-up externe ou interne)

// ============================================================================
//                  PARAMÈTRES PHYSIQUES (À CALIBRER !)
// ============================================================================
const float DIAMETRE_ROUE_MM  = 70.0f;   // diamètre de la roue codeuse (mm)
const int   TICKS_PAR_TOUR    = 1024 * 2; // ticks par tour (mode CHANGE x4 = 4096
                                          // pour un encodeur 1024 ppr ; ici on
                                          // garde votre formule actuelle)
const float ENTRAXE_MM        = 400.0f;  // distance entre les 2 roues codeuses (mm)

// Position initiale (sera surchargée par la Pi via SETPOS)
volatile float pos_x = 0.0f;        // mm
volatile float pos_y = 0.0f;        // mm
volatile float pos_theta = 0.0f;    // rad

// ============================================================================
//                          ODOMÉTRIE
// ============================================================================
volatile long ticks_L = 0;
volatile long ticks_R = 0;
long ticks_L_prev = 0;
long ticks_R_prev = 0;

void IRAM_ATTR updateEncoderL() {
  int stateA = digitalRead(PIN_ENC_L_A);
  if (stateA == digitalRead(PIN_ENC_L_B)) ticks_L++;
  else                                    ticks_L--;
}

void IRAM_ATTR updateEncoderR() {
  int stateA = digitalRead(PIN_ENC_R_A);
  if (stateA == digitalRead(PIN_ENC_R_B)) ticks_R++;
  else                                    ticks_R--;
}

// Convertit un delta de ticks en distance parcourue (mm)
inline float ticksToMm(long dticks) {
  return (float)dticks * PI * DIAMETRE_ROUE_MM / (float)TICKS_PAR_TOUR;
}

// Met à jour la pose (x, y, theta) à partir des deltas d'encodeurs
void updateOdometrie() {
  noInterrupts();
  long tL = ticks_L;
  long tR = ticks_R;
  interrupts();

  long dL_ticks = tL - ticks_L_prev;
  long dR_ticks = tR - ticks_R_prev;
  ticks_L_prev = tL;
  ticks_R_prev = tR;

  float dL = ticksToMm(dL_ticks);
  float dR = ticksToMm(dR_ticks);

  float d_centre = (dL + dR) * 0.5f;
  float d_theta  = (dR - dL) / ENTRAXE_MM;

  // Intégration sur le milieu du pas (formule classique)
  float theta_mid = pos_theta + d_theta * 0.5f;
  pos_x     += d_centre * cosf(theta_mid);
  pos_y     += d_centre * sinf(theta_mid);
  pos_theta += d_theta;

  // Garder theta dans [-PI, +PI]
  while (pos_theta >  PI) pos_theta -= 2.0f * PI;
  while (pos_theta < -PI) pos_theta += 2.0f * PI;
}

// ============================================================================
//                          SONARS HC-SR04
// ============================================================================
// On lit les 4 sonars en non-bloquant et en rotation (1 par cycle d'envoi)
// pour ne pas accumuler les délais d'attente d'écho (~30 ms max chacun).
struct Sonar {
  uint8_t trig;
  uint8_t echo;
  float   distance_mm;  // dernière distance mesurée
};

Sonar sonars[4] = {
  {PIN_SONAR1_TRIG, PIN_SONAR1_ECHO, 9999.0f},
  {PIN_SONAR2_TRIG, PIN_SONAR2_ECHO, 9999.0f},
  {PIN_SONAR3_TRIG, PIN_SONAR3_ECHO, 9999.0f},
  {PIN_SONAR4_TRIG, PIN_SONAR4_ECHO, 9999.0f}
};

// Lecture d'un sonar (bloquante, ~30 ms max)
float readSonar(uint8_t trig, uint8_t echo) {
  digitalWrite(trig, LOW);
  delayMicroseconds(2);
  digitalWrite(trig, HIGH);
  delayMicroseconds(10);
  digitalWrite(trig, LOW);

  // Timeout 25 ms -> distance max ~4 m
  unsigned long duration = pulseIn(echo, HIGH, 25000UL);
  if (duration == 0) return 9999.0f;   // pas d'écho

  // Vitesse du son ~ 343 m/s = 0.343 mm/µs. Aller-retour, donc /2.
  return (float)duration * 0.343f / 2.0f;
}

// ============================================================================
//                          SERVOS
// ============================================================================
Servo servo1, servo2, servo3, servo4, servo5;

// Bornes de sécurité (à ajuster selon la mécanique)
const int SERVO_MIN_US = 500;
const int SERVO_MAX_US = 2500;

// Angles "logiques" (par défaut au démarrage)
const int SERVO_FRONT_CLOSE  = 0;     // barrière avant levée -> on peut glisser sous les caisses
const int SERVO_FRONT_OPEN = 100;    // barrière avant baissée -> caisses calées sous le robot
const int SERVO_REAR_CLOSE  = 100;     // barrière arrière baissée -> les caisses restent
const int SERVO_REAR_OPEN   = 0;    // barrière arrière levée -> libération des caisses

void setServo(uint8_t id, int angle) {
  angle = constrain(angle, 0, 180);
  switch (id) {
    case 1: servo1.write(angle); break;
    case 2: servo2.write(angle); break;
    case 3: servo3.write(angle); break;
    case 4: servo4.write(angle); break;
    case 5: servo5.write(angle); break;
  }
}

void setAllFrontServos(int angle) {
  servo1.write(angle);
  servo2.write(angle);
  servo3.write(angle);
  servo4.write(angle);
}

// ============================================================================
//                          MOTEURS DC
// ============================================================================
void setMotor(uint8_t dirPin, uint8_t pwmChannel, int dir, int pwm) {
  pwm = constrain(pwm, 0, 255);
  digitalWrite(dirPin, dir ? HIGH : LOW);
  ledcWrite(pwmChannel, pwm);
}

void stopMotors() {
  ledcWrite(CH_PWM_MOT1, 0);
  ledcWrite(CH_PWM_MOT2, 0);
}

// ============================================================================
//                          ÉTAT DU MATCH (sécurité)
// ============================================================================
bool matchStarted = false;
bool emergencyStop = false;

// ============================================================================
//                          PARSEUR DE COMMANDES Pi -> ESP32
// ============================================================================
void handleCommand(const String& msg) {
  // MOT:dm1,pm1,dm2,pm2
  if (msg.startsWith("MOT:")) {
    if (emergencyStop) return;
    int v[4]; int idx = 0; int start = 4;
    for (int i = 4; i <= (int)msg.length() && idx < 4; i++) {
      if (i == (int)msg.length() || msg[i] == ',') {
        v[idx++] = msg.substring(start, i).toInt();
        start = i + 1;
      }
    }
    if (idx == 4) {
      setMotor(PIN_MOT1_DIR, CH_PWM_MOT1, v[0], v[1]);
      setMotor(PIN_MOT2_DIR, CH_PWM_MOT2, v[2], v[3]);
    }
  }
  // SRV:id,angle
  else if (msg.startsWith("SRV:")) {
    int sep = msg.indexOf(',', 4);
    if (sep > 0) {
      int id    = msg.substring(4, sep).toInt();
      int angle = msg.substring(sep + 1).toInt();
      setServo(id, angle);
    }
  }
  // SRVALL:a1,a2,a3,a4,a5
  else if (msg.startsWith("SRVALL:")) {
    int v[5]; int idx = 0; int start = 7;
    for (int i = 7; i <= (int)msg.length() && idx < 5; i++) {
      if (i == (int)msg.length() || msg[i] == ',') {
        v[idx++] = msg.substring(start, i).toInt();
        start = i + 1;
      }
    }
    if (idx == 5) {
      servo1.write(constrain(v[0], 0, 180));
      servo2.write(constrain(v[1], 0, 180));
      servo3.write(constrain(v[2], 0, 180));
      servo4.write(constrain(v[3], 0, 180));
      servo5.write(constrain(v[4], 0, 180));
    }
  }
  else if (msg == "STOP") {
    stopMotors();
  }
  else if (msg == "RESET") {
    noInterrupts();
    ticks_L = 0; ticks_R = 0;
    ticks_L_prev = 0; ticks_R_prev = 0;
    pos_x = 0; pos_y = 0; pos_theta = 0;
    interrupts();
  }
  // SETPOS:x,y,theta
  else if (msg.startsWith("SETPOS:")) {
    int s1 = msg.indexOf(',', 7);
    int s2 = msg.indexOf(',', s1 + 1);
    if (s1 > 0 && s2 > 0) {
      noInterrupts();
      pos_x     = msg.substring(7, s1).toFloat();
      pos_y     = msg.substring(s1 + 1, s2).toFloat();
      pos_theta = msg.substring(s2 + 1).toFloat();
      interrupts();
    }
  }
}

// ============================================================================
//                                  SETUP
// ============================================================================
void setup() {
  Serial.begin(115200);
  Serial2.begin(115200, SERIAL_8N1, PIN_RX2, PIN_TX2);

  // --- Encodeurs ---
  pinMode(PIN_ENC_L_A, INPUT_PULLUP);
  pinMode(PIN_ENC_L_B, INPUT_PULLUP);
  pinMode(PIN_ENC_R_A, INPUT_PULLUP);
  pinMode(PIN_ENC_R_B, INPUT_PULLUP);
  attachInterrupt(digitalPinToInterrupt(PIN_ENC_L_A), updateEncoderL, CHANGE);
  attachInterrupt(digitalPinToInterrupt(PIN_ENC_R_A), updateEncoderR, CHANGE);

  // --- Moteurs ---
  pinMode(PIN_MOT1_DIR, OUTPUT);
  pinMode(PIN_MOT2_DIR, OUTPUT);
  ledcAttach(PIN_MOT1_PWM, PWM_FREQ, PWM_RES);
  ledcAttach(PIN_MOT2_PWM, PWM_FREQ, PWM_RES);
  stopMotors();

  // --- Sonars ---
  for (int i = 0; i < 4; i++) {
    pinMode(sonars[i].trig, OUTPUT);
    pinMode(sonars[i].echo, INPUT);
    digitalWrite(sonars[i].trig, LOW);
  }

  // --- Servos (timers ESP32) ---
  ESP32PWM::allocateTimer(0);
  ESP32PWM::allocateTimer(1);
  ESP32PWM::allocateTimer(2);
  ESP32PWM::allocateTimer(3);
  servo1.setPeriodHertz(50); servo1.attach(PIN_SERVO1, SERVO_MIN_US, SERVO_MAX_US);
  servo2.setPeriodHertz(50); servo2.attach(PIN_SERVO2, SERVO_MIN_US, SERVO_MAX_US);
  servo3.setPeriodHertz(50); servo3.attach(PIN_SERVO3, SERVO_MIN_US, SERVO_MAX_US);
  servo4.setPeriodHertz(50); servo4.attach(PIN_SERVO4, SERVO_MIN_US, SERVO_MAX_US);
  servo5.setPeriodHertz(50); servo5.attach(PIN_SERVO5, SERVO_MIN_US, SERVO_MAX_US);

  // Position de départ des servos : barrières AVANT ouvertes,
  // barrière ARRIÈRE fermée. Le robot est prêt à glisser sous les caisses.
  setAllFrontServos(SERVO_FRONT_OPEN);
  servo5.write(SERVO_REAR_CLOSE);

  // --- Tirette / BAU ---
  pinMode(PIN_TIRETTE, INPUT_PULLUP);


  Serial.println("ESP32 gros robot pret.");
}

// ============================================================================
//                                  LOOP
// ============================================================================
void loop() {
  static unsigned long lastOdo   = 0;
  static unsigned long lastSonar = 0;
  static unsigned long lastPos   = 0;
  static uint8_t sonarIdx        = 0;
  unsigned long now = millis();

  // ----- 1. Odométrie : haute fréquence (~ toutes les 10 ms) -----
  if (now - lastOdo >= 10) {
    lastOdo = now;
    updateOdometrie();
  }

  // ----- 2. Envoi de la position à la Pi (~ toutes les 50 ms = 20 Hz) -----
  if (now - lastPos >= 50) {
    lastPos = now;
    Serial2.print("POS:");
    Serial2.print(pos_x, 1);   Serial2.print(',');
    Serial2.print(pos_y, 1);   Serial2.print(',');
    Serial2.println(pos_theta, 4);
  }

  // ----- 3. Lecture d'un sonar à la fois (rotation toutes les 25 ms) -----
  if (now - lastSonar >= 25) {
    lastSonar = now;
    sonars[sonarIdx].distance_mm = readSonar(sonars[sonarIdx].trig,
                                             sonars[sonarIdx].echo);
    sonarIdx = (sonarIdx + 1) % 4;

    // Quand on a fait un tour complet, on envoie le paquet sonar
    if (sonarIdx == 0) {
      Serial2.print("SONAR:");
      Serial2.print((int)sonars[0].distance_mm); Serial2.print(',');
      Serial2.print((int)sonars[1].distance_mm); Serial2.print(',');
      Serial2.print((int)sonars[2].distance_mm); Serial2.print(',');
      Serial2.println((int)sonars[3].distance_mm);
    }
  }

  // ----- 4. Lecture commandes Pi -> ESP32 -----
  if (Serial2.available()) {
    String msg = Serial2.readStringUntil('\n');
    msg.trim();
    if (msg.length() > 0) handleCommand(msg);
  }

  // ----- 5. Surveillance tirette de départ -----
  // La tirette est tirée -> passage HIGH (si pull-up) -> match commence
  static bool tiretteWasIn = true;
  bool tiretteIn = (digitalRead(PIN_TIRETTE) == LOW);
  if (tiretteWasIn && !tiretteIn && !matchStarted) {
    matchStarted = true;
    Serial2.println("EVT:START");
  }
  tiretteWasIn = tiretteIn;
}
