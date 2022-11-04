EESchema Schematic File Version 4
EELAYER 30 0
EELAYER END
$Descr A4 11693 8268
encoding utf-8
Sheet 2 2
Title "Off Board Components"
Date "2021-09-21"
Rev "A"
Comp "Chan Zuckerberg Biohub"
Comment1 "Bioengineering Platform"
Comment2 "PN: 5-005"
Comment3 ""
Comment4 ""
$EndDescr
$Comp
L Switch:SW_SPDT #SW?
U 1 1 64DF04EA
P 8855 2530
AR Path="/64DF04EA" Ref="#SW?"  Part="1" 
AR Path="/64D22535/64DF04EA" Ref="#SW3"  Part="1" 
F 0 "#SW3" H 8780 2680 50  0000 C CNN
F 1 "SW_SPDT" H 8805 2755 50  0000 C CNN
F 2 "" H 8855 2530 50  0001 C CNN
F 3 "https://sensing.honeywell.com/honeywell-micro-switch-zm-zm1-basic-product-sheet-004991-3-en.pdf" H 8855 2530 50  0001 C CNN
	1    8855 2530
	0    -1   -1   0   
$EndComp
NoConn ~ 8755 2330
$Comp
L Connector_Generic:Conn_01x02 #J?
U 1 1 64DF04FA
P 1855 1610
AR Path="/64DF04FA" Ref="#J?"  Part="1" 
AR Path="/64D22535/64DF04FA" Ref="#J25"  Part="1" 
F 0 "#J25" H 1935 1602 50  0000 L CNN
F 1 "LED" H 1935 1511 50  0000 L CNN
F 2 "" H 1855 1610 50  0001 C CNN
F 3 "https://www.molex.com/molex/products/part-detail/crimp_housings/2026542021" H 1855 1610 50  0001 C CNN
	1    1855 1610
	1    0    0    -1  
$EndComp
Text Notes 8315 1375 0    39   ~ 0
Servo comes with female headers, but we may need to replace it \nw/ the proper mating component for the male headers\nso that there is a good friction lock.
$Comp
L Connector_Generic:Conn_02x08_Counter_Clockwise #J?
U 1 1 64DF0502
P 1840 4140
AR Path="/64DF0502" Ref="#J?"  Part="1" 
AR Path="/64D22535/64DF0502" Ref="#J17"  Part="1" 
F 0 "#J17" H 1890 4657 50  0000 C CNN
F 1 "SHIELD SIDE CABLE" H 1890 4566 50  0000 C CNN
F 2 "" H 1840 4140 50  0001 C CNN
F 3 "https://www.digikey.com/en/products/detail/cnc-tech/3230-16-0104-00/3883520" H 1840 4140 50  0001 C CNN
	1    1840 4140
	1    0    0    -1  
$EndComp
$Comp
L Connector_Generic:Conn_02x08_Counter_Clockwise #J?
U 1 1 64DF0508
P 3955 4140
AR Path="/64DF0508" Ref="#J?"  Part="1" 
AR Path="/64D22535/64DF0508" Ref="#J18"  Part="1" 
F 0 "#J18" H 4005 4657 50  0000 C CNN
F 1 "REMOTE SIDE CABLE" H 4005 4566 50  0000 C CNN
F 2 "" H 3955 4140 50  0001 C CNN
F 3 "https://www.digikey.com/en/products/detail/cnc-tech/3230-16-0104-00/3883520" H 3955 4140 50  0001 C CNN
	1    3955 4140
	-1   0    0    -1  
$EndComp
Wire Wire Line
	2140 3840 3655 3840
Wire Wire Line
	2140 4040 3655 4040
Wire Wire Line
	2140 4240 3655 4240
Wire Wire Line
	2140 4440 3655 4440
Wire Wire Line
	2140 4540 3655 4540
Wire Wire Line
	2140 4340 3655 4340
Wire Wire Line
	2140 3940 3655 3940
Wire Wire Line
	2140 4140 3655 4140
Text Notes 2025 3450 0    30   ~ 0
Board to board cable assembly. Female-female IDC headers on a ribbon cable.
$Comp
L Device:LED #D?
U 1 1 64DF0549
P 1275 1675
AR Path="/64DF0549" Ref="#D?"  Part="1" 
AR Path="/64D22535/64DF0549" Ref="#D5"  Part="1" 
F 0 "#D5" V 1314 1754 50  0000 L CNN
F 1 "LED" V 1223 1754 50  0000 L CNN
F 2 "" H 1275 1675 50  0001 C CNN
F 3 "https://www.digikey.com/en/products/detail/lite-on-inc/LTPL-C034UVH405/5414489" H 1275 1675 50  0001 C CNN
	1    1275 1675
	0    -1   -1   0   
$EndComp
Wire Wire Line
	1655 1610 1655 1525
Wire Wire Line
	1655 1525 1275 1525
Wire Wire Line
	1275 1825 1655 1825
Wire Wire Line
	1655 1710 1655 1825
$Comp
L Motor:Motor_Servo #M?
U 1 1 64DF0553
P 8870 1825
AR Path="/64DF0553" Ref="#M?"  Part="1" 
AR Path="/64D22535/64DF0553" Ref="#M3"  Part="1" 
F 0 "#M3" H 8864 2169 50  0000 C CNN
F 1 "Motor_Servo" H 8864 2078 50  0000 C CNN
F 2 "" H 8870 1635 50  0001 C CNN
F 3 "https://www.pololu.com/file/0J508/HD-1810MG.pdf" H 8870 1635 50  0001 C CNN
	1    8870 1825
	-1   0    0    -1  
$EndComp
$Comp
L Connector_Generic:Conn_01x03 #J?
U 1 1 64DF0559
P 9485 1825
AR Path="/64DF0559" Ref="#J?"  Part="1" 
AR Path="/64D22535/64DF0559" Ref="#J27"  Part="1" 
F 0 "#J27" H 9485 2170 50  0000 C CNN
F 1 "SERVO" H 9440 2075 50  0000 C CNN
F 2 "" H 9485 1825 50  0001 C CNN
F 3 "https://www.molex.com/molex/products/part-detail/crimp_housings/0022012037" H 9485 1825 50  0001 C CNN
	1    9485 1825
	1    0    0    -1  
$EndComp
Wire Wire Line
	9170 1725 9285 1725
Wire Wire Line
	9170 1825 9285 1825
Wire Wire Line
	9170 1925 9285 1925
$Comp
L Motor:Stepper_Motor_bipolar #M?
U 1 1 64DF0562
P 6660 1930
AR Path="/64DF0562" Ref="#M?"  Part="1" 
AR Path="/64D22535/64DF0562" Ref="#M2"  Part="1" 
F 0 "#M2" H 6610 1705 50  0000 L CNN
F 1 "GM15BY-VSM1527-100-10D" H 6110 1605 50  0000 L CNN
F 2 "" H 6670 1920 50  0001 C CNN
F 3 "https://www.aliexpress.com/item/32978411412.html" H 6670 1920 50  0001 C CNN
	1    6660 1930
	0    1    1    0   
$EndComp
$Comp
L Connector_Generic:Conn_01x04 #J?
U 1 1 64DF0568
P 7610 1880
AR Path="/64DF0568" Ref="#J?"  Part="1" 
AR Path="/64D22535/64DF0568" Ref="#J26"  Part="1" 
F 0 "#J26" H 7528 1455 50  0000 C CNN
F 1 "STEPPER" H 7528 1546 50  0000 C CNN
F 2 "" H 7610 1880 50  0001 C CNN
F 3 "https://www.digikey.com/en/products/detail/molex/0151340400/6198146" H 7610 1880 50  0001 C CNN
	1    7610 1880
	1    0    0    1   
$EndComp
Wire Wire Line
	6560 1630 6560 1515
Wire Wire Line
	6560 1515 7300 1515
Wire Wire Line
	7300 1515 7300 1680
Wire Wire Line
	7300 1680 7410 1680
Wire Wire Line
	6760 1630 7260 1630
Wire Wire Line
	7260 1630 7260 1780
Wire Wire Line
	7260 1780 7410 1780
Wire Wire Line
	6960 2030 7410 2030
Wire Wire Line
	7410 2030 7410 1980
Wire Wire Line
	7410 1880 6960 1880
Wire Wire Line
	6960 1880 6960 1830
$Comp
L Connector_Generic:Conn_01x02 #J?
U 1 1 64DF0579
P 9480 2435
AR Path="/64DF0579" Ref="#J?"  Part="1" 
AR Path="/64D22535/64DF0579" Ref="#J21"  Part="1" 
F 0 "#J21" H 9560 2427 50  0000 L CNN
F 1 "LIMIT_SWITCH_1" H 9560 2336 50  0000 L CNN
F 2 "" H 9480 2435 50  0001 C CNN
F 3 "https://www.digikey.com/en/products/detail/adafruit-industries-llc/3922/9685337" H 9480 2435 50  0001 C CNN
	1    9480 2435
	1    0    0    -1  
$EndComp
Wire Wire Line
	8955 2330 9280 2330
Wire Wire Line
	9280 2330 9280 2435
Wire Wire Line
	8855 2730 9280 2730
Wire Wire Line
	9280 2730 9280 2535
$Comp
L Switch:SW_SPDT #SW?
U 1 1 64DF0583
P 8860 3110
AR Path="/64DF0583" Ref="#SW?"  Part="1" 
AR Path="/64D22535/64DF0583" Ref="#SW4"  Part="1" 
F 0 "#SW4" H 8785 3260 50  0000 C CNN
F 1 "SW_SPDT" H 8810 3335 50  0000 C CNN
F 2 "" H 8860 3110 50  0001 C CNN
F 3 "https://sensing.honeywell.com/honeywell-micro-switch-zm-zm1-basic-product-sheet-004991-3-en.pdf" H 8860 3110 50  0001 C CNN
	1    8860 3110
	0    -1   -1   0   
$EndComp
NoConn ~ 8760 2910
$Comp
L Connector_Generic:Conn_01x02 #J?
U 1 1 64DF058A
P 9485 3015
AR Path="/64DF058A" Ref="#J?"  Part="1" 
AR Path="/64D22535/64DF058A" Ref="#J22"  Part="1" 
F 0 "#J22" H 9565 3007 50  0000 L CNN
F 1 "LIMIT_SWITCH_2" H 9565 2916 50  0000 L CNN
F 2 "" H 9485 3015 50  0001 C CNN
F 3 "https://www.digikey.com/en/products/detail/adafruit-industries-llc/3922/9685337" H 9485 3015 50  0001 C CNN
	1    9485 3015
	1    0    0    -1  
$EndComp
Wire Wire Line
	8960 2910 9285 2910
Wire Wire Line
	9285 2910 9285 3015
Wire Wire Line
	8860 3310 9285 3310
Wire Wire Line
	9285 3310 9285 3115
$Comp
L Connector_Generic:Conn_01x05 #J?
U 1 1 64DF0595
P 7635 3270
AR Path="/64DF0595" Ref="#J?"  Part="1" 
AR Path="/64D22535/64DF0595" Ref="#J28"  Part="1" 
F 0 "#J28" H 7553 3687 50  0000 C CNN
F 1 "ENCODER" H 7553 3596 50  0000 C CNN
F 2 "" H 7635 3270 50  0001 C CNN
F 3 "https://www.digikey.com/en/products/detail/molex/5024390500/3260509" H 7635 3270 50  0001 C CNN
	1    7635 3270
	1    0    0    -1  
$EndComp
$Comp
L Motor:Fan #M?
U 1 1 64DF05AA
P 2650 1725
AR Path="/64DF05AA" Ref="#M?"  Part="1" 
AR Path="/64D22535/64DF05AA" Ref="#M1"  Part="1" 
F 0 "#M1" H 2492 1821 50  0000 R CNN
F 1 "Fan" H 2492 1730 50  0000 R CNN
F 2 "" H 2650 1735 50  0001 C CNN
F 3 "https://www.mechatronics.com/pdf/B5020.pdf" H 2650 1735 50  0001 C CNN
	1    2650 1725
	1    0    0    -1  
$EndComp
Wire Wire Line
	2650 1425 3130 1425
Wire Wire Line
	3130 1425 3130 1625
Wire Wire Line
	2650 1925 3130 1925
Wire Wire Line
	3130 1925 3130 1725
Wire Wire Line
	8925 3710 9275 3710
$Comp
L Connector_Generic:Conn_01x05 #J?
U 1 1 64DF05CA
P 1620 2625
AR Path="/64DF05CA" Ref="#J?"  Part="1" 
AR Path="/64D22535/64DF05CA" Ref="#J15"  Part="1" 
F 0 "#J15" H 1538 3042 50  0000 C CNN
F 1 "MPR_Pressure_Breakout" H 1538 2951 50  0000 C CNN
F 2 "" H 1620 2625 50  0001 C CNN
F 3 "~" H 1620 2625 50  0001 C CNN
	1    1620 2625
	-1   0    0    -1  
$EndComp
$Comp
L Connector_Generic:Conn_01x05 #J?
U 1 1 64DF05D0
P 2875 2625
AR Path="/64DF05D0" Ref="#J?"  Part="1" 
AR Path="/64D22535/64DF05D0" Ref="#J16"  Part="1" 
F 0 "#J16" H 2793 3042 50  0000 C CNN
F 1 "MPR_Pressure_Breakout_Conn" H 2793 2951 50  0000 C CNN
F 2 "" H 2875 2625 50  0001 C CNN
F 3 "https://www.digikey.com/en/products/detail/molex/0901560145/760736" H 2875 2625 50  0001 C CNN
	1    2875 2625
	1    0    0    -1  
$EndComp
Text Notes 915  2995 0    39   ~ 0
Use regular P2.54mm male pins on breakout board\n
Wire Wire Line
	1820 2425 2675 2425
Wire Wire Line
	1820 2525 2675 2525
Wire Wire Line
	1820 2625 2675 2625
Wire Wire Line
	1820 2725 2675 2725
Wire Wire Line
	1820 2825 2675 2825
Text Notes 7440 1055 0    59   ~ 0
Remote Board Components\n
Wire Wire Line
	9275 4010 9275 3930
Wire Wire Line
	8925 4010 9275 4010
Wire Wire Line
	9275 3710 9275 3830
$Comp
L Device:Electromagnetic_Actor L?
U 1 1 64DF05C0
P 8925 3810
AR Path="/64DF05C0" Ref="L?"  Part="1" 
AR Path="/64D22535/64DF05C0" Ref="#L3"  Part="1" 
F 0 "#L3" H 8795 3814 50  0000 R CNN
F 1 "VALVE" H 8795 3905 50  0000 R CNN
F 2 "" V 8900 3910 50  0001 C CNN
F 3 "~" V 8900 3910 50  0001 C CNN
	1    8925 3810
	1    0    0    1   
$EndComp
$Comp
L Connector_Generic:Conn_01x02 #J?
U 1 1 64DF05BA
P 9475 3830
AR Path="/64DF05BA" Ref="#J?"  Part="1" 
AR Path="/64D22535/64DF05BA" Ref="#J24"  Part="1" 
F 0 "#J24" H 9555 3822 50  0000 L CNN
F 1 "VALVE" H 9555 3731 50  0000 L CNN
F 2 "" H 9475 3830 50  0001 C CNN
F 3 "https://www.molex.com/molex/products/part-detail/crimp_housings/2026542021" H 9475 3830 50  0001 C CNN
	1    9475 3830
	1    0    0    -1  
$EndComp
Text Notes 1935 1110 0    59   ~ 0
Main Board Components\n
$Comp
L power:GND #PWR071
U 1 1 6605384F
P 6825 4465
F 0 "#PWR071" H 6825 4215 50  0001 C CNN
F 1 "GND" H 6830 4292 50  0000 C CNN
F 2 "" H 6825 4465 50  0001 C CNN
F 3 "" H 6825 4465 50  0001 C CNN
	1    6825 4465
	1    0    0    -1  
$EndComp
Wire Wire Line
	6825 4465 6670 4465
$Comp
L Switch:SW_SPST SW?
U 1 1 61673018
P 7125 4265
AR Path="/61673018" Ref="SW?"  Part="1" 
AR Path="/64D22535/61673018" Ref="#SW6"  Part="1" 
F 0 "#SW6" V 7175 4555 50  0000 R CNN
F 1 "12V_SWITCH" V 7100 4800 50  0000 R CNN
F 2 "" H 7125 4265 50  0001 C CNN
F 3 "https://www.digikey.com/en/products/detail/switch-components/RF1-1A-DC-2-R-1/11492837" H 7125 4265 50  0001 C CNN
	1    7125 4265
	1    0    0    -1  
$EndComp
$Comp
L Connector_Generic:Conn_01x02 #J?
U 1 1 6165AC7C
P 3330 1625
AR Path="/6165AC7C" Ref="#J?"  Part="1" 
AR Path="/64D22535/6165AC7C" Ref="#J23"  Part="1" 
F 0 "#J23" H 3410 1617 50  0000 L CNN
F 1 "FAN" H 3410 1526 50  0000 L CNN
F 2 "" H 3330 1625 50  0001 C CNN
F 3 "https://www.digikey.com/en/products/detail/molex/0510210200/242842?utm_adgroup=Connectors%20%26%20Interconnects&utm_source=google&utm_medium=cpc&utm_campaign=Dynamic%20Search_EN_Product&utm_term=&utm_content=Connectors%20%26%20Interconnects&gclid=CjwKCAjwtfqKBhBoEiwAZuesiFsxfBKkBfunjHFEX8ndclfE03LpsQ0aJ1bUUSo-KliiUNP-btW6HxoC67MQAvD_BwE" H 3330 1625 50  0001 C CNN
	1    3330 1625
	1    0    0    -1  
$EndComp
$Comp
L Connector_Generic:Conn_01x02 #J29
U 1 1 616CBECB
P 7890 4335
F 0 "#J29" H 7808 4552 50  0000 C CNN
F 1 "12V_WALL_CONN" H 7808 4461 50  0000 C CNN
F 2 "" H 7890 4335 50  0001 C CNN
F 3 "https://www.digikey.com/en/products/detail/te-connectivity-amp-connectors/1-480318-0/15664" H 7890 4335 50  0001 C CNN
	1    7890 4335
	1    0    0    -1  
$EndComp
Wire Wire Line
	7690 4265 7690 4335
Wire Wire Line
	7690 4435 7690 4465
$Comp
L Connector_Generic:Conn_01x05 #J?
U 1 1 6323F68B
P 7050 3270
AR Path="/6323F68B" Ref="#J?"  Part="1" 
AR Path="/64D22535/6323F68B" Ref="#J1"  Part="1" 
F 0 "#J1" H 6968 3687 50  0000 C CNN
F 1 "ENCODER" H 6968 3596 50  0000 C CNN
F 2 "" H 7050 3270 50  0001 C CNN
F 3 "https://shop.pimoroni.com/products/rgb-encoder-breakout" H 7050 3270 50  0001 C CNN
	1    7050 3270
	-1   0    0    -1  
$EndComp
Wire Wire Line
	7250 3070 7435 3070
Wire Wire Line
	7250 3170 7435 3170
Wire Wire Line
	7250 3270 7435 3270
Wire Wire Line
	7250 3370 7435 3370
Wire Wire Line
	7250 3470 7435 3470
$Comp
L power:+12V #PWR0134
U 1 1 625BA266
P 6825 4265
F 0 "#PWR0134" H 6825 4115 50  0001 C CNN
F 1 "+12V" H 6840 4438 50  0000 C CNN
F 2 "" H 6825 4265 50  0001 C CNN
F 3 "" H 6825 4265 50  0001 C CNN
	1    6825 4265
	1    0    0    -1  
$EndComp
Wire Wire Line
	6925 4265 6825 4265
Connection ~ 6825 4265
Wire Wire Line
	7325 4265 7690 4265
Wire Wire Line
	6825 4465 7690 4465
Connection ~ 6825 4465
$Comp
L Connector:Mini-DIN-4 #J19
U 1 1 62F0B693
P 6280 4415
F 0 "#J19" H 6280 4782 50  0000 C CNN
F 1 "Mini-DIN-4" H 6280 4691 50  0000 C CNN
F 2 "" H 6280 4415 50  0001 C CNN
F 3 "http://service.powerdynamics.com/ec/Catalog17/Section%2011.pdf" H 6280 4415 50  0001 C CNN
	1    6280 4415
	1    0    0    -1  
$EndComp
Wire Wire Line
	6580 4415 6580 4640
Wire Wire Line
	6580 4640 5980 4640
Wire Wire Line
	5980 4640 5980 4415
Wire Wire Line
	6670 4465 6670 4415
Wire Wire Line
	6670 4415 6580 4415
Connection ~ 6580 4415
Wire Wire Line
	6580 4265 6825 4265
Wire Wire Line
	6580 4095 5980 4095
Wire Wire Line
	5980 4095 5980 4315
Wire Wire Line
	6580 4095 6580 4265
Connection ~ 6580 4265
Wire Wire Line
	6580 4265 6580 4315
$Comp
L Motor:Fan #M?
U 1 1 62F1D246
P 8830 4550
AR Path="/62F1D246" Ref="#M?"  Part="1" 
AR Path="/64D22535/62F1D246" Ref="#M4"  Part="1" 
F 0 "#M4" H 8672 4646 50  0000 R CNN
F 1 "Fan" H 8672 4555 50  0000 R CNN
F 2 "" H 8830 4560 50  0001 C CNN
F 3 "https://www.mechatronics.com/pdf/B5020.pdf" H 8830 4560 50  0001 C CNN
	1    8830 4550
	1    0    0    -1  
$EndComp
Wire Wire Line
	8830 4250 9310 4250
Wire Wire Line
	9310 4250 9310 4450
Wire Wire Line
	8830 4750 9310 4750
Wire Wire Line
	9310 4750 9310 4550
$Comp
L Connector_Generic:Conn_01x02 #J?
U 1 1 62F1D250
P 9510 4450
AR Path="/62F1D250" Ref="#J?"  Part="1" 
AR Path="/64D22535/62F1D250" Ref="#J2"  Part="1" 
F 0 "#J2" H 9590 4442 50  0000 L CNN
F 1 "CAM_FAN1" H 9590 4351 50  0000 L CNN
F 2 "" H 9510 4450 50  0001 C CNN
F 3 "https://www.digikey.com/en/products/detail/molex/0510210200/242842?utm_adgroup=Connectors%20%26%20Interconnects&utm_source=google&utm_medium=cpc&utm_campaign=Dynamic%20Search_EN_Product&utm_term=&utm_content=Connectors%20%26%20Interconnects&gclid=CjwKCAjwtfqKBhBoEiwAZuesiFsxfBKkBfunjHFEX8ndclfE03LpsQ0aJ1bUUSo-KliiUNP-btW6HxoC67MQAvD_BwE" H 9510 4450 50  0001 C CNN
	1    9510 4450
	1    0    0    -1  
$EndComp
$Comp
L Motor:Fan #M?
U 1 1 62F21820
P 8830 5215
AR Path="/62F21820" Ref="#M?"  Part="1" 
AR Path="/64D22535/62F21820" Ref="#M5"  Part="1" 
F 0 "#M5" H 8672 5311 50  0000 R CNN
F 1 "Fan" H 8672 5220 50  0000 R CNN
F 2 "" H 8830 5225 50  0001 C CNN
F 3 "https://www.mechatronics.com/pdf/B5020.pdf" H 8830 5225 50  0001 C CNN
	1    8830 5215
	1    0    0    -1  
$EndComp
Wire Wire Line
	8830 4915 9310 4915
Wire Wire Line
	9310 4915 9310 5115
Wire Wire Line
	8830 5415 9310 5415
Wire Wire Line
	9310 5415 9310 5215
$Comp
L Connector_Generic:Conn_01x02 #J?
U 1 1 62F2182A
P 9510 5115
AR Path="/62F2182A" Ref="#J?"  Part="1" 
AR Path="/64D22535/62F2182A" Ref="#J3"  Part="1" 
F 0 "#J3" H 9590 5107 50  0000 L CNN
F 1 "CAM_FAN2" H 9590 5016 50  0000 L CNN
F 2 "" H 9510 5115 50  0001 C CNN
F 3 "https://www.digikey.com/en/products/detail/molex/0510210200/242842?utm_adgroup=Connectors%20%26%20Interconnects&utm_source=google&utm_medium=cpc&utm_campaign=Dynamic%20Search_EN_Product&utm_term=&utm_content=Connectors%20%26%20Interconnects&gclid=CjwKCAjwtfqKBhBoEiwAZuesiFsxfBKkBfunjHFEX8ndclfE03LpsQ0aJ1bUUSo-KliiUNP-btW6HxoC67MQAvD_BwE" H 9510 5115 50  0001 C CNN
	1    9510 5115
	1    0    0    -1  
$EndComp
Wire Wire Line
	1640 3840 1415 3840
Text Label 1415 3840 0    39   ~ 0
S1
Wire Wire Line
	1640 4040 1415 4040
Text Label 1415 4040 0    39   ~ 0
S2
Wire Wire Line
	1640 4240 1415 4240
Text Label 1415 4240 0    39   ~ 0
S3
Wire Wire Line
	1640 4440 1415 4440
Text Label 1415 4440 0    39   ~ 0
S4
Wire Wire Line
	1640 4340 1415 4340
Text Label 1415 4340 0    39   ~ 0
VALVE
Wire Wire Line
	1640 4540 1415 4540
Text Label 1415 4540 0    39   ~ 0
CAM_FAN1
$Comp
L power:+12V #PWR0139
U 1 1 62F4F166
P 1300 3940
F 0 "#PWR0139" H 1300 3790 50  0001 C CNN
F 1 "+12V" H 1315 4113 50  0000 C CNN
F 2 "" H 1300 3940 50  0001 C CNN
F 3 "" H 1300 3940 50  0001 C CNN
	1    1300 3940
	1    0    0    -1  
$EndComp
Wire Wire Line
	1300 3940 1640 3940
$Comp
L power:GND #PWR0145
U 1 1 62F54951
P 1305 4140
F 0 "#PWR0145" H 1305 3890 50  0001 C CNN
F 1 "GND" H 1310 3967 50  0000 C CNN
F 2 "" H 1305 4140 50  0001 C CNN
F 3 "" H 1305 4140 50  0001 C CNN
	1    1305 4140
	1    0    0    -1  
$EndComp
Wire Wire Line
	1305 4140 1640 4140
Wire Wire Line
	4155 3840 4380 3840
Text Label 4380 3840 2    39   ~ 0
S1
Wire Wire Line
	4155 4040 4380 4040
Text Label 4380 4040 2    39   ~ 0
S2
Wire Wire Line
	4155 4240 4380 4240
Text Label 4380 4240 2    39   ~ 0
S3
Wire Wire Line
	4155 4440 4380 4440
Text Label 4380 4440 2    39   ~ 0
S4
Wire Wire Line
	4155 4340 4380 4340
Text Label 4380 4340 2    39   ~ 0
VALVE
Wire Wire Line
	4155 4540 4380 4540
Text Label 4380 4540 2    39   ~ 0
CAM_FAN1
$Comp
L power:+12V #PWR0146
U 1 1 62F65746
P 4495 3940
F 0 "#PWR0146" H 4495 3790 50  0001 C CNN
F 1 "+12V" H 4510 4113 50  0000 C CNN
F 2 "" H 4495 3940 50  0001 C CNN
F 3 "" H 4495 3940 50  0001 C CNN
	1    4495 3940
	-1   0    0    -1  
$EndComp
Wire Wire Line
	4495 3940 4155 3940
$Comp
L power:GND #PWR0147
U 1 1 62F6574D
P 4490 4140
F 0 "#PWR0147" H 4490 3890 50  0001 C CNN
F 1 "GND" H 4495 3967 50  0000 C CNN
F 2 "" H 4490 4140 50  0001 C CNN
F 3 "" H 4490 4140 50  0001 C CNN
	1    4490 4140
	-1   0    0    -1  
$EndComp
Wire Wire Line
	4490 4140 4155 4140
$EndSCHEMATC
