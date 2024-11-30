<!--
Markdown Guide: https://www.markdownguide.org/basic-syntax/
-->
<!--
Disable markdownlint errors:
fenced-code-language MD040
no-inline-html MD033
-->
<!-- markdownlint-disable MD040 MD033-->

# EVBilling

**evbilling** - produce EV charger submeter bills for the PG&E BEV-1 rate schedule

# SYNOPSIS

**evbilling** [**-h** | **--help**] [**--autoblock** | **--no-autoblock**]
[**-d** | **--debug** | **--no-debug**] [**--fixocr** | **--no-fixocr**]
[**--forceocr** | **--no-forceocr**] [**--outdir** *DIRECTORY*] [**--pages**
*PAGES*] [**--print** | **--no-print**] [**-q** | **--quiet** | **--no-quiet**]
[**--showocr** | **--no-showocr**] [**--submeter** | **--no-submeter**] [**-v**
| **--version** | **--no-version**]
**FILES ...**

# DESCRIPTION

**evbilling** produces bills for Electric Vehicle (EV) chargers connected to the
EV power panel at The Palace at Washington Square condominium in San Francisco,
CA.  The EV power panel is equipped with an [Emporia Vue 3 energy
monitor](https://shop.emporiaenergy.com/products/emporia-vue-3-3-phase-energy-management-hub-monitor-with-8-sensors).
Input is a Pacific Gas & Electric (PG&E) BEV-1 rate schedule bill in PDF format
downloaded from [pge.com](https://www.pge.com/).

The **evbilling** program:

1. performs Optical Character Recognition (OCR) on a Pacific Gas &
    Electric/CleanPowerSF PDF bill to obtain billing periods, rates, and
    charges;
2. writes an OCR **sidecar** text file, which can be edited if necessary to
    correct OCR errors;
3. downloads hourly usage data for the billing period for the individual EV
    chargers from the Emporia Vue server; and
4. writes EV charger PDF and plain text submeter bill files, accounting for
    rate changes and varying Time-Of-Use (TOU) rates.

**evbilling** writes the following files to a directory named *yyyy*-*mm*-*dd*
that it creates in the current directory or in the directory specified by the
**--outdir** argument, where *yyyy*-*mm*-*dd* is the statement date of the bill
file (see ARGUMENTS below):

* *nnnn*custbill*mmddyyyy*.pdf -- a copy of the PG&E bill file.
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
* *nnnn*custbill*mmddyyyy*-*circuit*.csv -- a CSV (Comma Separated Values) file
  of the raw usage data, formatted as a day-by-hour matrix, for each *circuit*
  connected to the EV power panel.
* *nnnn*custbill*mmddyyyy*.zip -- a .zip file containing all PDF bill files.

**evbilling** also writes a log file named **evbilling.log** to the conventional
OS-dependent log directory, `C:\Users\`*`Username`*`\AppData\Local\EVBilling\Logs` on
Windows.

# OPTIONS

**-h, --help**
:   Print a help message and exit.

**--autoblock, --no-autoblock**
:   Automatically locate OCR text blocks; default --autoblock.

**-d, --debug, --no-debug**
:   Log debugging information; default --no-debug.

**--fixocr, --no-fixocr**
:   Fix obvious OCR errors; default --fixocr.

**--forceocr, --no-forceocr**
:   Force PDF Optical Character Recognition (OCR); default --no-forceocr.

**--outdir** *directory*
:   Output directory, default current working directory

**--pages** *ij*
:   Two single-digit page numbers, *i* is the *Details of PG&E
 Electric Delivery Charges* page number and *j* is the *Details of CleanPowerSF
 Electric Generation Charges* page number; default: 34.

**--print, --no-print**
:   Print PG&E bill OCR text to `stdout`; default: --no-print.

**-q, --quiet, --no-quiet**
:   Do not print INFO, WARNING, ERROR, or CRITICAL messages to `stderr`; default --no-quiet.

**--showocr, --no-showocr**
:   Show OCR result; implies **--forceocr**; default --no-showocr.

**--submeter, --no-submeter**
:   Write PDF submeter bills; default --submeter.

**-v, --version, --no-version**
:   Display the version number and exit.

# ARGUMENTS

*FILES* :   List of PG&E PDF bill files to be processed.  *FILES* must have the
format *nnnn*custbill*mmddyyyy*.pdf, where *nnnn* is the last four digits of the
PG&E account number and *mmddyyyy* is the PG&E bill statement date.

# SETTINGS

Settings for **evbilling** are configured in the **evbilling.toml** file in the
conventional OS-dependent data directory,
`C:\Users\`*`Username`*`\AppData\Roaming\EVBilling` on Windows.

See [TOML: A config file format for humans](https://toml.io/en/) for the
**.toml** file format specification.

## [credentials]

### contact_email

```
# Email address to appear in submeter bill footer
contact_email = "pws.ev.energy@gmail.com"
```

### ev_system and ev_username

```
# keyring arguments for the Emporia Vue server
ev_system = "emporiavue"
ev_username = "pws.ev.energy@gmail.com"
```

These settings are used to retrieve the Emporia Vue server account password from
the PC's keyring.  Set the Emporia Vue password with the command:
<pre>
keyring set "<i>ev_system</i>" "<i>ev_username</i>"
</pre>
For example:

```
keyring set "emporiavue" "pws.ev.energy@gmail.com"
```

## [ev_chargers]

The `[ev_chargers]` section describes the EVSE (Electric Vehicle Service
Equipment) power ratings in kW.

```
PWS-304-P05 = 1.92  # NEMA 5-15R, 3030-PSE-16-7.7C-AS charging cable, nominal 120V*16A
PWS-404-P06 = 1.45  # NEMA 5-!5R, Toyota G9060-47130 charging cable, measured June, 2024
PWS-502-P07 = 6.66  # Tesla 80A, nominal 208V*32A
PWS-405-P14 = 8.32  # Tesla Gen3, nominal 208V*40A
PWS-403-P20 = 6.66  # Tesla 80A, nominal 208V*32A
"""EVSE (Electric Vehicle Service Equipment) power ratings in kW."""
```

The PG&E BEV-1 rate schedule includes a **subscription** (a.k.a **demand**)
**charge** based on a measurement of the maximum kW power usage in any single
15-minute period during a monthly billing cycle.  The subscription level is
purchased in blocks of 10 kW, and the charge is apportioned to the EV chargers
based on their kW power ratings.

The EV charger names (keys) in the `[ev_chargers]` setting must match the
circuit names configured in the Emporia Vue application, and the corresponding
values are the EV charger power ratings in kW.  This setting must be updated
whenever EV chargers are connected, disconnected, or replaced.  Initially, the
nominal charger power rating can be set, but should be updated to the actual
value as measured by the Emporia Vue application.

**NB: Whenever the load on the EV power panel changes, contact the PG&E Solar
department at 877-743-4112 and ask to be transferred to Solar/EV Business
department to adjust the number of 10 kW blocks and request a grace period.
From [PG&E Electric Schedule BEV, SPECIAL CONDITIONS, 7. GRACE
PERIOD](https://www.pge.com/tariffs/assets/pdf/tariffbook/ELEC_SCHEDS_BEV.pdf):

*GRACE PERIOD: A grace period is a period of three (3) billing cycles, each
with a minimum of 27 days, in which a BEV customer is not subject to overage
fees (see “Special Conditions” section, item 8) associated with exceeding the
customer’s monthly pre-defined kW subscription. A grace period is triggered
under the following two conditions:*
<i>

1. <b>Customer Enrollment</b>: A grace period is triggered when a customer
    enrolls in a BEV rate.
2. <b>Addition of Electrical Vehicle Service Equipment (EVSE)</b>: After a
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

## [policy]

### include_kW_limit

```
# Include excess subscription charges in submeter bills if
# sum(EV charger power ratings) > include_kW_limit.
include_kW_limit = 5.0  # kW
```

Since the subscription level is purchased in blocks of 10 kW, it will generally
exceed the total maximum power demand of all EV chargers. The `include_kW_limit`
setting determines if the excess subscription is apportioned to the EV chargers
based on their kW power ratings, or if the excess is excluded from submeter
bills.  Its purpose is to keep charging costs economical when there are only one
or two low-power chargers, such as those for PHEVs, connected to the EV power
panel.

## [tariffs]

The `[tariffs]` section controls from where **evtariffs** downloads tariffs and
where it stores them.

```
# URL of PG&E BEV PDF tariff file for evtariffs command
pge_bev_tariff_url = """
https://www.pge.com/tariffs/assets/pdf/tariffbook/ELEC_SCHEDS_BEV.pdf"""

# PG&E BEV tariff download directory for evtariffs command on PalaceSecurity PC:
pge_bev_tariff_dir = 'C:\Users\Palace_security\OneDrive - Grayson Community Management\General - PWS External\Documents\Maintenance and Services\PG&E\Tariffs\BEV'

```

## [links]

The `[links]` section contains links to websites with information about tariffs,
rates, credits, taxes, fees, and surcharges. The **evtariffs** command downloads
tariffs from the `pge_bev_tariff_url` and saves these in the
`pge_bev_tariff_dir` for use by **evbilling**.  Other links are shown in the
*Further information* sections on the PG&E and CleanpowerSF details pages.

Links should be kept current.

```
# URL of PG&E BEV PDF tariff file for evtariffs command
pge_bev_tariff_url = """
https://www.pge.com/tariffs/assets/pdf/tariffbook/ELEC_SCHEDS_BEV.pdf"""

# PG&E BEV tariff download directory for evtariffs command
pge_bev_tariff_dir = '\\NAS0\Household\Household Documents\1731 Powell\HOA\PWS Collaboration\Documents\Maintenance and Services\PG&E\Tariffs\BEV'

# Further information links:

pge_electric_schedule_bev1 = """[PG&E Electric Schedule BEV-1]\
(https://www.pge.com/tariffs/assets/pdf/tariffbook/ELEC_SCHEDS_BEV.pdf)"""

pge_commercial_bev_tariffs = """[Commercial Business Electric Vehicle (BEV) Rates]\
(https://www.pge.com/tariffs/en/rate-information/electric-rates.html#accordion-a84c67dc1e-item-69d101345a)"""

cpsf_commercial_rates = """[CleanPowerSF Commercial Rates, B-EV-1, p.5]\
(https://static1.squarespace.com/static/5a79fded4c326db242490272/t/66845b3e64535d5bbbb39dbe/1719950143549/CPSF+Commercial+Rates+2024.pdf)"""

sf_franchise_fee_surcharge  = """[Franchise Fee Surcharge]\
(https://sfcontroller.org/sites/default/files/Documents/Auditing/BOS%20PGE%20Franchise%20Fee%20Audit%20Report%20%202.23.21.pdf)"""

sf_utility_users_tax = """[San Francisco Utility Users Tax]\
(https://sfgov.org/lafco/sites/default/files/FileCenter/Documents/52280-4%20City%20and%20County%20of%20San%20Francisco%20Controller%E2%80%99s%20Office%20%28April%202005%29%20The%20Utility%20Users%20Tax.pdf)"""

sf_prop_c_tax_surcharge = """[SF Prop C Tax Surcharge]\
(https://sftreasurer.org/business/taxes-fees/homelessness-gross-receipts-tax-hgr)"""

energy_commission_surcharge = """[Energy Commission Surcharge]\
(https://www.cdtfa.ca.gov/formspubs/L924.pdf)"""

evbilling_source = """[EV Billing Software Version {__version__}](https://github.com/kgorlen/EVBilling)"""

# 'Further information' PG&E links in submeter bill PDF files:
pge_reference_urls = [
    "pge_electric_schedule_bev1",
    "pge_commercial_bev_tariffs",
    "sf_franchise_fee_surcharge",
    "sf_utility_users_tax",
    "sf_prop_c_tax_surcharge",
    "evbilling_source",
]

# 'Further information' CleanPowerSF links in submeter bill PDF files:
cpsf_reference_urls = [
    "cpsf_commercial_rates",
    "sf_utility_users_tax",
    "energy_commission_surcharge",
    "evbilling_source",
]
```

## [time_of_use]

The `[time_of_use]` section defines the hours when *Super Off Peak* and *Peak*
Time Of Use (TOU) rates are in effect.  All other hours are assumed to be billed
at *Off Peak* rates.

```
"Super Off Peak" = [[9, 14]]    # 9:00am to 2:00pm
"Peak" = [[16, 21]]             # 4:00pm to 9:00pm
# All other hours are "Off Peak"
```

Hours are numbered from 0 (midnight to 1:00am) to 23 (11:00pm to midnight). The
notation [*i*, *j*] defines a range of hours from hour *i* to hour *j*-1, and
the ending hour must be larger than the starting hour (i.e. [*i*, *j*] is
converted to the Python `range(i, j)`).  Multiple ranges can be specified for a
TOU rate period; for example, the following defines the two-hour TOU range from
11:00pm to 1:00am:

```
"Super Off Peak" = [[23, 24], [0, 1]]
```

## [rate_info]

### cpsf_rate_change

The `cpsf_rate_change` setting defines the month and day when CleanPowerSF
annually updates electric generation rates.  See *CleanPowerSF Rate Changes*
for details.

```
# Date of CleanPowerSF annual rate change
cpsf_rate_change = "7/1"
```

# INSTALLATION

## ENVIRONMENT

Set `FONTCONFIG_PATH` to `C:\Users\`*`Username`*`\.config\fontconfig` in
the User environment.

`C:\Users\`*`Username`*`\.config\fontconfig` should include a **fonts.conf** file, e.g.:

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

## PREREQUISITES

[Install python 3.12 or later version](https://www.python.org/downloads/).

Install [pipx](https://pipx.pypa.io/stable/):

```
pip install pipx
```

Install [keyring](https://pypi.org/project/keyring/):

```
pipx install keyring
```

## INSTALL **evbilling** FROM `.whl` package

<pre>
<code>pipx install <i>path</i>\evbilling-<i>version</i>-py3-none-any.whl</code>
</pre>

For example:

<pre>
<code>pipx install <i>path</i>\evbilling-0.1.5-py3-none-any.whl</code>
</pre>

## INSTALL **evbilling** FROM `.tar.gz` package

Alternatively, install **evbilling** from a `.tar.gz` package file:

<pre>
<code>pipx install <i>path</i>\evbilling-<i>version</i>.tar.gz</code>
</pre>

For example:

<pre>
<code>pipx install <i>path</i>\evbilling-0.1.5-.tar.gz</code>
</pre>

## CONFIGURE **evtariffs**

The **evtariffs** command downloads the PG&E tariff PDF files required by
**evbilling** and prepends the tariff effective date to the PDF filename:

```
usage: evtariffs.py [-h] [-d | --debug | --no-debug] [-q | --quiet | --no-quiet] [-v | --version | --no-version] [DIRECTORY]

Download PG&E BEV tariffs and order by effective date

positional arguments:
  DIRECTORY             Output directory; default "C:\Users\<User>\.evbilling\tariffs"

options:
  -h, --help            show this help message and exit
  -d, --debug, --no-debug
                        Log debug info; default --no-debug
  -q, --quiet, --no-quiet
                        Do not print verbose output; default --quiet
  -v, --version, --no-version
                        Display the version number and exit

```

Schedule the **evtariffs** command to be run at least weekly so that newly
published tariffs are not missed.

**evtariffs** writes a log file named **evtariffs.log** to the conventional
OS-dependent log directory, `C:\Users\`*`Username`*`\AppData\Local\EVBilling\Logs`
on Windows.

**Note:** The *DIRECTORY* argument is used only for testing since **evbilling**
expects tariffs to be found in the **pge_bev_tariff_dir** configured in
**evbilling.toml** (see *SETTINGS*).

## CONFIGURE **runevbilling**

Optionally, **runevbilling** can be configured for use with the *Windows File
Explorer* *Open with ...* menu to allow **evbilling** to be run on a PG&E PDF
bill file without needing to launch a **cmd** window and enter a command.

To configure **runevbilling**:

1. Browse with Windows File Explorer to the folder containing the PG&E PDF bill
   file to be processed.
1. Right-click on the bill file and choose *Open with* -> *Choose another app*.
1. Scroll to the bottom and choose *More apps*.
1. Scroll to the bottom and choose *Look for another app on this PC*.
1. Browse to `C:\Users\`*`Username`*`\.local\bin`.
1. Open **runevbilling.exe**.

This will run **evbilling** on the bill file and add **runevbilling.exe** to the
*Choose another app* menu for future use.

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

# EXPLANATION OF SUBMETER BILL LINE ITEMS

A submeter bill consists of three pages, described in the following sections.

The header of every page contains the submeter *Account* name, the *Statement
Date* from the corresponding PG&E main bill, and the *Due Date*, which is the
first day of the month after the *Statement Date*.

The footer of every page has the contact email address and the date on which
the submeter bill was produced.

## Submeter Bill Page 1

**Charger Power Rating**
: Charger power rating in kW, obtained from **evsettings.py**.

**Total Usage**
: Total charger energy usage for the billing period in kWh, as measured by the
submeter.

**PG&E Electric Delivery Charges**
: Total PG&E Electric Delivery Charges from page 2.

**CleanPowerSF Electric Generation Charges**
: Total CleanPowerSF Electric Generation Charges from page 3.

**Metering Difference Adjustment**
: Adjustment for the difference between the PG&E panel meter reading and the sum of the individual submeter readings.  Formula:

```
[(PG&E main bill Total Amount Due) - sum(All submeter PG&E and CleanPowerSF charges)]
                           *(Submeter Total Usage)
-------------------------------------------------------------------------------------
                         (PG&E main bill Total Usage)
```

**Total Amount Due**
: Sum of submeter PG&E Electric Delivery Charges, CleanPowerSF Electric
Generation Charges, and the Metering Difference Adjustment.

**Effective Rate**
: (Total Amount Due/Total Usage)

**Cost Breakdown Chart**
: Pie chart showing cost and percentage of the submeter bill for Peak kWh, Off
Peak kWh, Super Off Peak kWh, Subscription Charge and any Overage Fees, and
Taxes & Fees for the billing period.

**Energy Usage Cost Chart**
: Stacked bar chart showing Peak kWh cost, Off Peak kWh cost, Super Off Peak kWh cost,
and Subscription cost for each day of the billing period.  All costs include taxes & fees,
and all energy (kWh) usage costs include the Metering Difference Adjustment.

**Monthly kWh Usage Chart**
: Stacked bar chart showing Peak kWh, Off Peak kWh, and Super Off Peak kWh energy
usage for the current month and the previous 12 months.

## Submeter Bill Page 2: Details of PG&E Electric Delivery Charges

**Subscription Level**
: Cost based on the Charger Power Rating from page 1.  Formula:

```
                                     (Charger Power Rating in kW)
(Number 10kW blocks)*Months*Rate*------------------------------------
                                 sum(All Charger Power Ratings in kW)

```

If the sum(All Charger Power Ratings in kW) is below the `INCLUDE_kW_LIMIT`:

```
                                  (Charger Power Rating in kW)
(Number 10kW blocks)*Months*Rate*------------------------------
                                    Subscription Level in kW

```

**Overage Fees**
: Fees charged for exceeding the Subscription Level kW peak power demand.
Formula:

```
(PG&E main bill Overage Fees charge)*(Charger Power Rating in kW)
-----------------------------------------------------------------
              sum(All Charger Power Ratings in kW)

```

Overage Fees are **excluded** if the sum(All Charger Power Ratings in kW) is
below the `INCLUDE_kW_LIMIT`.

**PG&E Energy Charges**
: Peak, Off Peak, and Super Off Peak kWh costs based on submeter kWh
measurements.

**PG&E Energy Credits**
: Credit rates are obtained from the BEV-1 tariff in effect during the billing
period.

***Peak, Off Peak, and Super Off Peak generation credits***
: Credits due to electric generation by CleanPowerSF instead of PG&E. Formula:

```
-(Generation Credit rate $/kWh)*(Peak, Off Peak, or Super Off Peak kWh)
```

***Bundled Power Charge Indifference Adjustment (PCIA) credit***
: Credit against the Vintaged Power Charge Indifference Adjustment. Formula:

```
(Bundled Power Charge Indifference Adjustment rate $/kWh)*(Submeter Total Usage kWh)
```

**Total Generation Credit**
: Sum of the PG&E Energy Credits.

**Power Charge Indifference Adjustment**
: Addition to PG&E costs to compensate for PG&E generation assets stranded by
CleanPowerSF customers. The PCIA is determined by the "vintage" year that a
customer started to obtain power from CleanPowerSF.  Formula:

```
(PG&E main bill Power Charge Indifference Adjustment charge)
------------------------------------------------------------*(Submeter Total Usage kWh)
             (PG&E main bill Total Usage kWh)

```

**Net Charges**
: Sum of Subscription Level charge, Subscription Overage Fees, PG&E Energy Charges,
Total Generation Credit, and Power Charge Indifference Adjustment.

**Franchise Fee Surcharge**
: Collect the fee PG&E pays to San Francisco for use of city streets to
transmit, distribute, and supply electricity.  Formula:

```
(PG&E main bill Franchise Fee Surcharge)
----------------------------------------*(Submeter Total Usage kWh)
    (PG&E main bill Total Usage kWh)

```

**San Francisco Utility Users' Tax**
: Collect the tax PG&E pays to San Francisco for non-residential electricity
consumption.  Formula:

```
(PG&E main bill San Francisco Utility Users' Tax)
----------------------------------------*(Submeter Net Charges)
       (PG&E main bill Net Charges)

```

**SF Prop C Tax Surcharge**
: Collect the tax PG&E pays to San Francisco to fund its homelessness programs.
Formula:

```
(PG&E main bill SF Prop C Tax Surcharge)
----------------------------------------*(Submeter Net Charges)
       (PG&E main bill Net Charges)

```

## Submeter Bill Page 3: Details of CleanPowerSF Electric Generation Charges

**CleanPowerSF Energy Charges**
: Peak, Off Peak, and Super Off Peak kWh costs based on submeter kWh
measurements.

**Net Charges**
: Sum of CleanPowerSF Energy Charges.

**Local Utility Users Tax**
: Collect the tax CleanPowerSF pays to San Francisco for non-residential electricity
consumption.  Formula:

```
(CleanPowerSF main bill Local Utility Users' Tax)
-------------------------------------------------*(Submeter Net Charges)
       (CleanPowerSF main bill Net Charges)

```

**Energy Commission Surcharge**
: Collect the tax CleanPowerSF pays to California for consumption of electrical
energy.  Formula:

```
(CleanPowerSF main bill Energy Commission Surcharge)
----------------------------------------------------*(Submeter Net Charges)
         (CleanPowerSF main bill Net Charges)

```

## CleanPowerSF Rate Changes

CleanPowerSF changes rates annually on July 1\*.  Unlike PG&E rates changes, these
are combined in a single rate period on the PG&E bill, which **evbilling**
splits into two rate periods, the first ending on June 30 and the second
beginning on July 1, assuming that the first and second rates listed for each
TOU period are the rates for the first and second rate periods, respectively.
If rates are missing due to no usage during a TOU period, **evbilling** stops
and the missing rates must looked up from previous bills or on [CleanPowerSF
Commercial Rates, B-EV-1,
p.5](https://static1.squarespace.com/static/5a79fded4c326db242490272/t/66845b3e64535d5bbbb39dbe/1719950143549/CPSF+Commercial+Rates+2024.pdf)
and manually entered in the **sidecar** file.

\*Update the `cpsf_rate_change` setting if CleanPowerSF changes the date of its
annual rate update.

# SEE ALSO

* [Emporia Energy Help Center](https://help.emporiaenergy.com/en/)<br>
* [Emporia Account Login](https://web.emporiaenergy.com/login)<br>
* [PG&E Electric Schedule BEV](https://www.pge.com/tariffs/assets/pdf/tariffbook/ELEC_SCHEDS_BEV.pdf)<br>
* [Commercial Business Electric Vehicle (BEV) Rates](https://www.pge.com/tariffs/en/rate-information/electric-rates.html#accordion-a84c67dc1e-item-69d101345a)<br>
* [CleanPowerSF Commercial Rates, B-EV-1, p.5](https://static1.squarespace.com/static/5a79fded4c326db242490272/t/66845b3e64535d5bbbb39dbe/1719950143549/CPSF+Commercial+Rates+2024.pdf)<br>
* [SF Franchise Fee Surcharge](https://sfcontroller.org/sites/default/files/Documents/Auditing/BOS%20PGE%20Franchise%20Fee%20Audit%20Report%20%202.23.21.pdf)<br>
* [San Francisco Utility Users' Tax (7.500%)](https://sfgov.org/lafco/sites/default/files/FileCenter/Documents/<br>52280-4%20City%20and%20County%20of%20San%20Francisco%20Controller%E2%80%99s%20Office%20%28April%202005%29%20The%20Utility%20Users%20Tax.pdf)<br>
* [SF Prop C Tax Surcharge](https://docs.cpuc.ca.gov/PublishedDocs/Published/G000/M329/K157/329157496.docx#:~:text=In%20the%20November%202018%20general,of%20%2410%20million%20for%202019.)<br>
* [Energy Commission Surcharge](https://www.cdtfa.ca.gov/formspubs/L924.pdf)<br>
* [PyEmVue -- Unofficial library for interacting with the Emporia Vue energy monitor](https://pypi.org/project/pyemvue/)<br>
* [docTR: Document Text Recognition](https://mindee.github.io/doctr/latest/index.html)<br>
* [TOML: A config file format for humans](https://toml.io/en/)<br>

# AUTHOR

Keith Gorlen<br>
<gorlen@comcast.net>

# COPYRIGHT

Copyright (c) 2024 Keith Gorlen<br>
All Rights Reserved
