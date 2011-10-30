/* -*- Mode: C; tab-width: 4; indent-tabs-mode: t; c-basic-offset: 4 -*- */
/*******************************************************************
 * Streaming from an analog input using ISR
 *
 * sampling frequency = 16e6/(64*256) ~ 977Hz
 *
 *******************************************************************/

#define INIT_TIMER_COUNT 6
#define RESET_TIMER2 TCNT2 = INIT_TIMER_COUNT

int ainPin = 0;
int dt = 10;

void setup() {

    Serial.begin(2000000);

    //Timer2 Settings: Timer Prescaler /64,
    TCCR2A |= (1<<CS22);
    TCCR2A &= ~((1<<CS21) | (1<<CS20));

    // Use normal mode
    TCCR2A &= ~((1<<WGM21) | (1<<WGM20));
    // Use internal clock - external clock not used in Arduino
    ASSR |= (0<<AS2);
    //Timer2 Overflow Interrupt Enable
    TIMSK2 |= (1<<TOIE2) | (0<<OCIE2A);
    RESET_TIMER2;
    sei();

}

void loop() {
    delay(dt);
}

ISR(TIMER2_OVF_vect) {

    static uint32_t cnt = 0;
    int val;

    // Read analog input and print to serial port (include a count)
    val = analogRead(ainPin);
    Serial.print(cnt,DEC);
    Serial.print(" ");
    Serial.println(val,DEC);
    cnt += 1;
}
