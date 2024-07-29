# EVBilling
**evbilling** - produce EV charger submeter bills for PG&E BEV-1 rate schedule

# SYNOPSIS
**evbilling** [**-h** | **--help**] [**--autoblock** | **--no-autoblock**]
[**--copybill** | **--no-copybill**] [**-d** | **--debug** | **--no-debug**]
[**--fixocr** | **--no-fixocr**] [**--ocr** | **--no-ocr**] [**--page PAGE**]
[**--print** | **--no-print**] [**-q** | **--quiet** | **--no-quiet**]
[**--showocr** | **--no-showocr**] [**--submeter** | **--no-submeter**] **FILE**
[**DIRECTORY**]

# DESCRIPTION
**evbilling** produces bills for Electric Vehicle (EV) chargers connected to the
EV power panel at The Palace at Washington Square condominium in San Francisco,
CA.  The EV power panel is equipped with an [Emporia Vue 3 energy
monitor](https://shop.emporiaenergy.com/products/emporia-vue-3-3-phase-energy-management-hub-monitor-with-8-sensors).
Input is a Pacific Gas & Electric (PG&E) BEV-1 rate schedule bill in PDF format
downloaded from [pge.com](https://www.pge.com/).

The **evbilling** program:

1.  performs Optical Character Recognition (OCR) on a Pacific Gas &
    Electric/CleanPowerSF PDF bill to obtain billing periods, rates, and
    charges;
2.  writes an OCR **sidecar** text file, which can be edited if necessary to
    correct OCR errors;
3.  downloads hourly usage data for the billing period for the individual EV
    chargers from the Emporia Vue server; and
4.  writes EV charger PDF and plain text submeter bill files, accounting for
    rate changes and varying Time-Of-Use (TOU) rates.

**evbilling** writes the following files to a directory named *yyyy*-*mm*-*dd*
that it creates in the current directory or in the directory specified by the
*DIRECTORY* argument, where *yyyy*-*mm*-*dd* is the statement date of the bill
file (see ARGUMENTS below):

* *nnnn*custbill*mmddyyyy*.pdf -- a copy of the PG&E bill file unless
  **--no-copybill** is specified.
* *nnnn*custbill*mmddyyyy*-OCR.txt -- the OCR result **sidecar** text file for
  the PG&E bill.
* *nnnn*custbill*mmddyyyy*.txt -- a plain text version of the PG&E bill, created
  if OCR completes without errors.
* *nnnn*custbill*mmddyyyy*-*circuit*.pdf -- a PDF submeter bill for each
  *circuit* connected to the EV power panel.  The *circuit* names configured
  with the Emporia Vue app have the format PWS-*uuu*-P*nn*, where *uuu* is the
  Owner's Unit number and *nn* is the EV charger parking space number.
* *nnnn*custbill*mmddyyyy*-*circuit*.txt -- a plain text submeter bill for each
  *circuit* connected to the EV power panel.

**evbilling** also writes a log file named **evbilling.log** to the current
directory or to the directory specified by the *DIRECTORY* argument.

# OPTIONS
**-h, --help**
:   Print a help message and exit.

**--autoblock**
:   Automatically locate OCR text blocks; default True.

**--copybill**
:   Copy the PG&E bill PDF file to the output directory; default True.

**-d, --debug**
:   Log debugging information; default False.

**--fixocr**
:   Fix obvious OCR errors; default True.

**--ocr**
:   Force PDF Optical Character Recognition (OCR); default False.

**--output** *directory*
:   Submeter bill output directory; default: current directory.

**--page** *number*
:   PG&E Electric Delivery Charges page number; default: 3.

**--print**
:   Print PG&E bill OCR text to `stdout`; default: False.

**-q, --quiet**
:   Do not print INFO, WARNING, ERROR, or CRITICAL messages to `stderr`; default False.

**--showocr**
:   Show OCR result; implies **--ocr**; default False.

**--submeter**
:   Write PDF submeter bills; default True.

# ARGUMENTS
*FILE* :   The PG&E PDF bill file to be processed.  *FILE* must have the format
*nnnn*custbill*mmddyyyy*.pdf, where *nnnn* is the last four digits of the PG&E
account number and *mmddyyyy* is the PG&E bill statement date.

*DIRECTORY* :   Output directory, default current working directory.

# SETTINGS

Edit the **evsettings.py** module to change the settings used by **evbilling**.

## CONTACT_EMAIL
```
CONTACT_EMAIL = 'pws.ev.energy@gmail.com'
"""Email address to appear in submeter bill footer."""
```

## EV_SYSTEM and EV_USERNAME
```
EV_SYSTEM = 'emporiavue'
EV_USERNAME = 'pws.ev.energy@gmail.com'
"""keyring arguments for the Emporia Vue server."""
```
These settings are used to retrieve the Emporia Vue server account password from
the PC's keyring.  Set the Emporia Vue password with the command:
<pre>
keyring set "<i>EV_SYSTEM</i>" "<i>EV_USERNAME</i>"
</pre>
For example:
```
keyring set "emporiavue" "pws.ev.energy@gmail.com"
```

## EVSE_kW_RATINGS
```
EVSE_kW_RATINGS = {
    'PWS-304-P05':120*16/1000,  # NEMA 5-15R, 3030-PSE-16-7.7C-AS charging cable, nominal
    'PWS-404-P06':1.46,         # NEMA 5-!5R, Toyota G9060-47130 charging cable, measured June, 2024
    'PWS-502-P07':208*40/1000,  # Tesla 80A, nominal
    'PWS-405-P14':208*48/1000,  # Tesla Gen3, nominal
    'PWS-403-P20':208*40/1000,  # Tesla 80A, nominal
    }
"""EVSE (Electric Vehicle Service Equipment) power ratings in kW."""
```
The PG&E BEV-1 rate schedule includes a **subscription** (a.k.a **demand**)
**charge** based on a measurement of the maximum kW power usage in any single
15-minute period during a monthly billing cycle.  The subscription charge is
purchased in blocks of 10 kW, and the charge is apportioned to the EV chargers
based on their kW power ratings.

The EV charger names (keys) in the `EVSE_kW_RATING` setting must match the
circuit names configured in the Emporia Vue application, and the corresponding
values are the EV charger power ratings in kW.  This setting must be updated
whenever EV chargers are connected, disconnected, or replaced.  Initially, the
nominal charger power rating can be set, but should be updated to the actual
value as measured by the Emporia Vue application.

PG&E should be notified whenever the load on the EV power panel changes.  From
[PG&E Electric Schedule BEV, SPECIAL CONDITIONS, 7. GRACE
PERIOD](https://www.pge.com/tariffs/assets/pdf/tariffbook/ELEC_SCHEDS_BEV.pdf):

*GRACE PERIOD: A grace period is a period of three (3) billing cycles, each
with a minimum of 27 days, in which a BEV customer is not subject to overage
fees (see “Special Conditions” section, item 8) associated with exceeding the
customer’s monthly pre-defined kW subscription. A grace period is triggered
under the following two conditions:*
<i>

1.  <b>Customer Enrollment</b>: A grace period is triggered when a customer
    enrolls in a BEV rate.
2.  <b>Addition of Electrical Vehicle Service Equipment (EVSE)</b>: After a
    customer is enrolled in BEV rate, a second qualifying event for grace
    periods is if an existing customer enrolled on the BEV rate (either BEV-1 or
    BEV-2 rate option) adds additional charging infrastructure that increases
    load. In this case, a customer must notify PG&E that they have increased the
    amount of EVSE infrastructure behind the meter, which will then trigger a
    grace period.

</i>

Failure to notify PG&E can incur an OVERAGE FEE, as described in [PG&E Electric
Schedule BEV, SPECIAL CONDITIONS, 8. OVERAGE/OVERAGE
FEE](https://www.pge.com/tariffs/assets/pdf/tariffbook/ELEC_SCHEDS_BEV.pdf).

**NOTE**: **evbilling** will require modification to process an OVERAGE FEE
if/when one is incurred, since it is not known how this fee will appear on a
BEV-1 rate schedule bill.

## CPSF_RATE_CHANGE
```
CPSF_RATE_CHANGE = '7/1'
"""Date of CleanPowerSF annual rate change."""
```

## TOU_HOURS
```
TOU_HOURS = {Tou.SUPER_OFF_PEAK:    [range(9, 12+2)],
             Tou.PEAK:              [range(12+4, 12+9)],
             }
"""Time-Of-Use hourly ranges."""
```
The `TOU_HOURS` table defines the hours to which various Time-Of-Use (TOU) $/kWh
rates apply.  The table associates TOU names (keys) with corresponding lists of
hourly ranges (values).  For example, the entry:
```
             Tou.SUPER_OFF_PEAK:    [range(9, 12+2)],
```
associates the "Super Off Peak" TOU period with the range of hours from 9 AM (9)
to 2 PM (12+2).

`Tou.OFF_PEAK` is set automatically to be all hours other than those defined in
`TOU_HOURS`.

# ENVIRONMENT
`FONTCONFIG_PATH` should be set to `C:\Users\`*`User`*`\.config\fontconfig` in
the User environment.

`C:\Users\`*`User`*`\.config\fontconfig` should include a **fonts.conf** file, e.g.:
```markdown

    <?xml version="1.0"?>
    <!DOCTYPE fontconfig SYSTEM "fonts.dtd">
    <fontconfig>
    <dir>C:/Windows/Fonts</dir>
    <cachedir>C:/Users/Your User Name Here/AppData/Local/fontconfig/cache</cachedir>
    <config>
        <rescan>
            <int>30</int>
        </rescan>
    </config>
    </fontconfig>
```
Run the following command to build font information cache files:
```
fc-cache -fv
```

# EXAMPLES
Most options are intended for testing and debugging.  After downloading a PG&E
bill named e.g. 2318custbill06132024.pdf, the command:
```
evbilling 2318custbill06132024.pdf
```
will create a subdirectory named **2024-06-13** to which it will write all files
as described earlier, including the submeter PDF bill files to be sent to the
Owners.

OCR is not 100% accurate, so **evbilling** may fail because it cannot find the
keywords it requires, or dates are inconsistent, or charges are missing or do
not reconcile, in which case it reports problems and stops.  It is then
necessary to manually correct the OCR **sidecar** file and rerun the
**evbilling** command.  In this example, the **sidecar** file would be named
**2318custbill06132024-OCR.txt**.

When run, **evbilling** checks for an existing **sidecar** file and uses it
instead of performing OCR on the PG&E bill.  It may be necessary to correct and
rerun the command repeatedly until all OCR errors have been corrected.  For
example, suppose **evbilling** fails:
```
evbilling 2318custbill07162024.pdf
2024-07-27 15:42:13 - CRITICAL - Missing 1011044609 PG&E charges: {'Franchise Fee Surcharge'}.; exiting.
```
The **2318custbill07162024-OCR.txt** file may then contain the excerpt:
```
=== Page 3 details ===
Details of PG&E Electric Delivery Charges
06/08/2024 - 07/09/2024 (32 billing days)
Service For: 1731 POWELL ST HSE EV CHARGER
Service Agreement ID: 3758116729
Rate Schedule: BEV1 Bus Low Use EV
06/08/2024 - 06/30/2024
Subscription Charges 1
Subscription Level (10kW/block) 10 blocks @ 0.7188 month @ $12.41 $89.20
Overage Fees 0 kW @ $2.48000 0.00
Energy Charges
Peak 1.904500 kWh @ $0.40040 0.12
Off Peak 17.028000 kWh @ $0.20938 3.55
Super Off Peak 2.518500 kWh @ $0.18173 0.46
Generation Credit -3.14
Power Charge Indifference Adjustment 0.17
Franchise e Fee Surcharge 0.02
San Francisco Utility Users' Tax (7.500%) 6.82
SF Prop C Tax Surcharge 0.90
```
The problem is the "e" between "Franchise" and "Fee".*  After editing
 **2318custbill07162024-OCR.txt** with e.g. Notepad to remove the 'e',
**evbilling** is rerun and fails again:
```
2024-07-27 15:44:41 - ERROR - Invalid 1011044609 PG&E charge:  Peak 1.804500 kWh @ $0.40040 $ 0.12
2024-07-27 15:44:41 - ERROR - Calculated PG&E total charges $135.96 not equal to OCR total charges $136.56
2024-07-27 15:44:41 - ERROR - 2 error(s) found while processing 2318custbill07162024.pdf.
2024-07-27 15:44:41 - CRITICAL - For details see log file: Testing\evbilling.log.; exiting.
```
Comparing the invalid PG&E charge to the original bill shows that the Peak
energy charge should be $0.72 instead of $0.12.  After correcting this error,
**evbilling** runs without errors.

Even if **evbilling** runs without errors, the plain text version of the PG&E
bill, which in this example would be named **2318custbill06132024.txt**, should
be compared to the downloaded bill to assure accuracy.

*OCR actually makes this type of error, but the **evbilling --fixocr** option
corrects these "obvious" errors before writing the **sidecar** file.

# LIMITATIONS
## Generation Credit
It is unclear how the Generation Credit is calculated.  Applying the unbundled
TOU generation energy rates from [PG&E Electric Schedule
BEV-1](https://www.pge.com/tariffs/assets/pdf/tariffbook/ELEC_SCHEDS_BEV.pdf) to
the metered TOU energy usage kWh does not agree with PG&E bills, so the rate is
calculated as *Generation Credit/Total Usage* and applied to submeter bills.

## Taxes and Surcharges
Tax and surcharge rates on PG&E bills generally do not agree with tariffs,
so **evbilling** calculates these rates and shows them in parentheses in
line items.  From the 6/8/2024 - 6/30/2024 billing period, for example:
```
Power Charge Indifference Adjustment ($0.00796/kWh)           $    0.17
Franchise Fee Surcharge (0.094% $/kWh)                        $    0.02
San Francisco Utility Users' Tax (7.498%)                     $    0.23
SF Prop C Tax Surcharge (0.989%)                              $    0.03
Local Utility Users Tax (7.463%)                              $    0.14
Energy Commission Surcharge ($0.00047/kWh)                    $    0.01
```
In this example:
```
Charge                                  Should Be
------                                  ---------
Power Charge Indifference Adjustment    $0.00809/kWh
Franchise Fee Surcharge                 0.5% $/kWh
San Francisco Utility Users' Tax        7.500% Net
SF Prop C Tax Surcharge                 0.986% Net
Local Utility Users Tax                 7.500% Net
Energy Commission Surcharge             $0.0003/kWh
```

## CleanPowerSF Rate Changes
CleanPowerSF changes rates annually on July 1.  Unlike PG&E rates changes, these
are combined in a single rate period on the PG&E bill, which **evbilling**
splits into two rate periods, the first ending on June 30 and the second
beginning on July 1, assuming that the first and second rates listed for each
TOU period are the rates for the first and second rate periods, respectively.
If rates are missing due to no usage during a TOU period, **evbilling** stops
and the missing rates must looked up from previous bills or on [CleanPowerSF
Commercial Rates, B-EV-1,
p.5](https://static1.squarespace.com/static/5a79fded4c326db242490272/t/66845b3e64535d5bbbb39dbe/1719950143549/CPSF+Commercial+Rates+2024.pdf)
and manually entered in the **sidecar** file.

# SEE ALSO
* [Emporia Energy Help Center](https://help.emporiaenergy.com/en/)<br>
* [Emporia Account Login](https://web.emporiaenergy.com/login)<br>
* [PG&E Electric Schedule BEV-1](https://www.pge.com/tariffs/assets/pdf/tariffbook/ELEC_SCHEDS_BEV.pdf)<br>
* [Commercial Business Electric Vehicle (BEV) Rates](https://www.pge.com/tariffs/en/rate-information/electric-rates.html#accordion-a84c67dc1e-item-69d101345a)<br>
* [CleanPowerSF Commercial Rates, B-EV-1, p.5](https://static1.squarespace.com/static/5a79fded4c326db242490272/t/66845b3e64535d5bbbb39dbe/1719950143549/CPSF+Commercial+Rates+2024.pdf)<br>
* [SF Franchise Fee Surcharge](https://sfcontroller.org/sites/default/files/Documents/Auditing/BOS%20PGE%20Franchise%20Fee%20Audit%20Report%20%202.23.21.pdf)<br>
* [San Francisco Utility Users' Tax (7.500%)](https://sfgov.org/lafco/sites/default/files/FileCenter/Documents/<br>52280-4%20City%20and%20County%20of%20San%20Francisco%20Controller%E2%80%99s%20Office%20%28April%202005%29%20The%20Utility%20Users%20Tax.pdf)<br>
* [SF Prop C Tax Surcharge](https://docs.cpuc.ca.gov/PublishedDocs/Published/G000/M329/K157/329157496.docx#:~:text=In%20the%20November%202018%20general,of%20%2410%20million%20for%202019.)<br>
* [Energy Commission Surcharge](https://www.cdtfa.ca.gov/formspubs/L924.pdf)<br>
* [PyEmVue -- Unofficial library for interacting with the Emporia Vue energy monitor](https://pypi.org/project/pyemvue/)<br>
* [docTR: Document Text Recognition](https://mindee.github.io/doctr/latest/index.html)<br>

# AUTHOR
Keith Gorlen<br>
gorlen@comcast.net

# COPYRIGHT
Copyright (c) 2024 Keith Gorlen<br>
All Rights Reserved
