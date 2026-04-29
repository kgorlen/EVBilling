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

**evbilling** [**-h** | **--help**]
[**-d** | **--debug** | **--no-debug**]
[**--link** | **--no-link**]
[**--maxscore** *MAXSCORE*]
[**--outdir** *DIRECTORY*]
[**--pages** *PAGES*]
[**--print** | **--no-print**]
[**-q** | **--quiet** | **--no-quiet**]
[**-v** | **--version** | **--no-version**]
**FILES ...**

# DESCRIPTION

**evbilling** produces bills for Electric Vehicle (EV) chargers connected to the
EV power panel at The Palace at Washington Square condominium building in San
Francisco, CA.  The EV power panel is equipped with an [Emporia Vue 3 energy
monitor](https://shop.emporiaenergy.com/products/emporia-vue-3-3-phase-energy-management-hub-monitor-with-8-sensors).
Inputs are Pacific Gas & Electric (PG&E) BEV-1 rate schedule bills in PDF format
downloaded from [pge.com](https://www.pge.com/) and Business Electric Vehicles
tariffs downloaded from
[pge.com/tariffs](https://www.pge.com/tariffs/assets/pdf/tariffbook/ELEC_SCHEDS_BEV.pdf).

The **evbilling** program:

1. extracts plain text from a Pacific Gas & Electric/CleanPowerSF searchable PDF
    bill to obtain billing periods, rates, and charges;
2. downloads hourly usage data for the billing period and historical data for
    the individual EV chargers from the Emporia Vue server;
3. writes EV charger PDF and plain text submeter bill files, accounting for
    rate changes and varying Time-Of-Use (TOU) rates.

**evbilling** writes the following files to a directory named *yyyy*-*mm*-*dd*
that it creates in the directory of the bill file or in the directory specified
by the **--outdir** argument, where *yyyy*-*mm*-*dd* is the statement date of
the bill file (see ARGUMENTS below):

* *nnnn*custbill*mmddyyyy*.pdf -- a copy of the PG&E bill file.
* *nnnn*custbill*mmddyyyy*.txt -- a plain text version of the PG&E bill, created
  if processing completes without errors, used for regression tests.
* *nnnn*custbill*mmddyyyy*.zip -- a .zip file containing all PDF bill files and
  the *nnnn*custbill*mmddyyyy*-DUE.csv file, used for billing.
* *nnnn*custbill*mmddyyyy*-DUE.json -- a CSV file containing the total amount
  due for each *circuit*.
* *nnnn*custbill*mmddyyyy*-EVE.json -- a JSON (JavaScript Object Notation) file
  containing a copy of the charger configuration used to process the PG&E bill,
  used for regression tests.
* *nnnn*custbill*mmddyyyy*-EXT.txt -- text extracted from the searchable PDF
  bill file.
* *nnnn*custbill*mmddyyyy*-*circuit*.pdf -- a PDF submeter bill for each
  *circuit* connected to the EV power panel.
* *nnnn*custbill*mmddyyyy*-*circuit*.txt -- a plain text submeter bill for each
  *circuit* connected to the EV power panel, used for regression tests.
* *nnnn*custbill*mmddyyyy*-*circuit*.csv -- a CSV (Comma Separated Values) file
  of the hourly usage data and daily costs for each *circuit* connected to the
  EV power panel, useful for calculating prorated costs.

**evbilling** also writes a log file named **evbilling.log**.  See **SETTINGS
[logging]** for details.

# OPTIONS

**-h, --help**
:   Print a help message and exit.

**-d, --debug, --no-debug**
:   Log debugging information; default --no-debug.

**--link, --no-link**
:   Link PDF bill input file to standard name file instead of renaming it; default: --no-link.

**--maxscore** *MAXSCORE*
:   Maximum normalized Levenshtein distance of recognizable extracted text lines; default: 0.2.

**--outdir** *directory*
:   Output directory; default: directory of PG&E .pdf bill

**--pages** *ij*
:   Two single-digit page numbers, *i* is the *Details of PG&E
 Electric Delivery Charges* page number and *j* is the *Details of CleanPowerSF
 Electric Generation Charges* page number; default: 34.

**--print, --no-print**
:   Print PG&E bill extracted text to `stdout`; default: --no-print.

**-q, --quiet, --no-quiet**
:   Do not print INFO, WARNING, ERROR, or CRITICAL messages to `stderr`; default --no-quiet.

**-v, --version, --no-version**
:   Display the version number and exit.

# ARGUMENTS

*FILES* :   List of directories or PG&E PDF bill files to be processed.  *FILES*
must have the bill ID format *xxxxxxxx*-*xxxx*-*xxxx*-*xxxx*-*xxxxxxxxxxxx*.pdf
where *x* is a digit or letter a-f OR the standardized name format
*nnnn*custbill*mmddyyyy*.pdf, where *nnnn* is the last four digits of the PG&E
account number and *mmddyyyy* is the PG&E bill statement date.  *FILES* with the
bill ID format are renamed to the standardized format.  If a directory is
specified, all bill files in the directory will be processed.

# EMPORIA APP OR WEBSITE SETTINGS

EV charger names, power ratings, service start date, channels, and owner email
addresses are configured with the Emporia Vue app or website under *Manage/Setup
Devices -> Energy and Circuits*.

## EV Charger Names, Power Ratings, Service Start Dates, and Owner Email Addresses

The PG&E BEV-1 rate schedule includes a **subscription** (a.k.a **demand**)
**charge** based on a measurement of the maximum kW power usage in any single
15-minute period during a monthly billing cycle.  The subscription level is
purchased in blocks of 10 kW, and the charge is apportioned to the EV chargers
based on their power (kW) ratings.

EV charger circuit names starting with "OFF" are ignored.  Power ratings are
specified by following the circuit name with space and the power rating in
kilowatts (kW). Text after "kW" is ignored.  For example circuit names for The
Palace have the format PWS-*uuu*-P*nn* *d.dd*kW *mm*/*dd*/*yyyy* #*breakers* *description* [*emails*] where:<br>
> *uuu* is the Owner's Unit number<br>
> *nn* is the EV charger parking space number<br>
> *d.d* is the power rating of the EV charger<br>
> *mm*/*dd*/*yyyy* is the service start date<br>
> *breaker* is a list of the circuit's breakers<br>
> *description* is a description of the EV charger<br>
> [*emails*] is a comma-separated list of Owner email addresses for use by **mailevbills**.

For example:

```
PWS-203-P07 2.7kW 4/23/2025 #19,21 (Tesla 80A) [owner203@gmail.com]
PWS-204-P26 7.1kW 5/27/2025 #20,22 (GM PowerUp) [owner204@comcast.net]
PWS-403-P20 6.7kW 2/21/2025 #13,15 (Tesla 80A) [owner403@gmail.com, coowner403@gmail.com]
PWS-404-P06 1.5kW 6/13/2024 #8 (NEMA 5-15R, Toyota G9060-47130) [owner404@outlook.com]
PWS-405-P14 8.1kW 2/21/2025 #14,16 (Tesla Gen3) [owner405@apple.com,coowner405@yahoo.com]
OFF PWS-304-P05 2.0kW #17 (NEMA 5-15R, 3030-PSE-16-7.7C-AS, nominal 120V*16A)
```

The circuit name without the power rating appears as the account name on
submeter bills.

EV charger circuits must be updated whenever EV chargers are connected,
disconnected, or replaced.  Initially, the nominal charger power rating can be
set; however, **evbilling** will attempt to determine the metered charger power
rating from recent 15-minute average kWh usage data.  It will use the metered
power rating if it is close (see [power_rating](#power_rating)) to the nominal
power rating; otherwise it will use the the nominal power rating and log a
WARNING message.

**NB**: Whenever the load on the EV power panel changes, contact the PG&E Solar
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

## Merged Circuits

Merged Circuits are used to monitor chargers powered by multiple phases.
Recommended practice is to use the same circuit name, without the kW rating or
comment, for all circuits merged to create a Merged Circuit.  For example, if
Circuits 1 and 2 are merged to create a Merged Circuit named `PWS-405-P14 8.5kW
 #14,16 (Tesla Gen3, measured Feb., 2025)`, Circuits 1 and 2 should be named
`PWS-405-P14`.

# **evbilling** SETTINGS

Settings for **evbilling** are configured in the **evbilling.toml** file in the conventional OS-dependent
data directory, `C:\Users\`*`Username`*`\AppData\Roaming\EVBilling` on Windows.

See [TOML: A config file format for humans](https://toml.io/en/) for the
**.toml** file format specification.

## [header]

The optional `[header]` section specifies the title and thumbnail image shown on
submeter bill PDF page headers.

### title

```
title = "The Palace at Washington Square\nEV Charger Energy Statement"
```

### thumbnail

```
thumbnail = "The-Palace-at-Washington-Square.jpg"
```

`thumbnail` may be either a .jpg or .png file in the conventional OS-dependent
data directory, `C:\Users\`*`Username`*`\AppData\Roaming\EVBilling` on Windows.

## [credentials]

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

## [contacts]

The required `[contacts]` section sets email addresses used by **evbilling**
and **mailevbills**.

### contact_email

```
# Email address to appear in submeter bill footer and mailevbills sender address
contact_email = "pws.ev.energy@gmail.com"
```

### billing_emails

```
# List of email addresses to which **mailevbills** sends amounts due table
# and the *nnnn*custbill*mmddyyyy*.zip file
billing_emails = ["pws.ev.energy@gmail.com", "billing_dept@mybuilding.com"]
```

## [smtp]

```
[smtp]
# SMTP server configuration
smtp_server = "smtp.gmail.com"
smtp_port = 465
smtp_user = "pws.ev.energy@gmail.com"
```

These settings specify the SMTP server used by **mailevbills** to email bills to
EV charger owners.  Set the SMTP server password with the command:
<pre>
keyring set "<i>smtp_server</i>" "<i>smtp_user</i>"
</pre>
For example:

```
keyring set "smtp.gmail.com" "pws.ev.energy@gmail.com"
```

## [logging]

The optional `[logging]` section sets where rotating log files are written. If
omitted, log files are written to the conventional OS-dependent log directory,
`C:\Users\`*`Username`*`\AppData\Local\EVBilling\Logs` on Windows.

```
evbilling = "\\NAS0\home\git\Keith\EVBilling\Testing\evbilling.log"
evtariffs = "\\NAS0\home\git\Keith\EVBilling\Testing\evtariffs.log"
mailevbills = '\\NAS0\home\git\Keith\EVBilling\Tests\mailevbills.log'
```

## [tariffs]

The `[tariffs]` section controls from where **evtariffs** downloads tariffs,
where it stores them, and the *Ping key* assigned by
[healthchecks.io](https://healthchecks.io/).

```
# URL of PG&E BEV PDF tariff file for evtariffs command
pge_bev_tariff_url = """
https://www.pge.com/tariffs/assets/pdf/tariffbook/ELEC_SCHEDS_BEV.pdf"""

# PG&E BEV tariff download directory for evtariffs command for testing on GBR-PC:
pge_bev_tariff_dir = '\\NAS0\Household\Household Documents\1731 Powell\HOA\PWS Collaboration\Documents\Maintenance and Services\PG&E\Tariffs\BEV'

# Ping key assigned by https://healthchecks.io/
healthchecks_uuid = "https://hc-ping.com/**********************"
```

See **CONFIGURE evtariffs** in **INSTALLATION**.

## [links]

The `[links]` section contains links to websites with information about tariffs,
rates, credits, taxes, fees, and surcharges. The **evtariffs** command downloads
tariffs from the `pge_bev_tariff_url` and saves these in the
`pge_bev_tariff_dir` for use by **evbilling**.  Other links are shown in the
*Further information* sections on the PG&E and CleanpowerSF details pages.

Links should be kept current.

```
# Further information links:

pge_electric_schedule_bev1 = """[PG&E Electric Schedule BEV-1]\
(https://www.pge.com/tariffs/assets/pdf/tariffbook/ELEC_SCHEDS_BEV.pdf)"""

pge_commercial_bev_tariffs = """[Commercial Business Electric Vehicle (BEV) Rates]\
(https://www.pge.com/tariffs/en/rate-information/electric-rates.html#accordion-a84c67dc1e-item-69d101345a)"""

cpsf_commercial_rates = """[CleanPowerSF Commercial Rates, B-EV-1, p.5]\
(https://static1.squarespace.com/static/5a79fded4c326db242490272/t/686427014729f246508ae08c/1751394050402/CPSF%2BCommercial%2BRates%2B2025.pdf)"""

sf_franchise_fee_surcharge  = """[Franchise Fee Surcharge]\
(https://help.pge.com/s/article/What-is-a-Franchise-Fee-Surcharge?language=en_US)"""

sf_utility_users_tax = """[San Francisco Utility Users Tax]\
(https://sfgov.org/lafco/sites/default/files/FileCenter/Documents/52280-4%20City%20and%20County%20of%20San%20Francisco%20Controller%E2%80%99s%20Office%20%28April%202005%29%20The%20Utility%20Users%20Tax.pdf)"""

sf_prop_c_tax_surcharge = """[SF Prop C Tax Surcharge]\
(https://sftreasurer.org/business/taxes-fees/homelessness-gross-receipts-tax-hgr-0)"""

energy_commission_surcharge = """[Energy Commission Surcharge]\
(https://cdtfa.ca.gov/formspubs/l1020.pdf)"""

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

## [power_rating]

The optional `[power_rating]` section sets parameters for measuring EV charger
power ratings from 15-minute average kWh usage data.  Data values less than
`sample_min_kWh` are ignored as idle power usage or noise.  If the metered power
rating differs from the nominal power rating specified in the circuit name
(see [EV Charger Names](#ev-charger-names-power-ratings-service-start-dates-and-owner-email-addresses))
by more than `tolerance_kW`, the nominal power rating is used with a warning
message. Default values are shown in this example:

```
"samples" = 4           # Number of 15-minute kWh samples to use
"sample_min_kW" = 1.0   # 15-minute kW sample threshold
"tolerance_kW" = 0.25   # Metered charger power rating tolerance
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
published tariffs are not missed.  When run, **evtariffs** sends a ping message
to [healthchecks.io](https://healthchecks.io/).  See the [healthchecks.io
documentation](https://healthchecks.io/docs/) for instructions for setting up an
account and obtaining a *Ping key*, which is used to set the **healthchecks_key**
in the **[tariffs]** section of the **evbilling.toml** file.

**evtariffs** writes a log file named **evtariffs.log**.  See **SETTINGS
[logging]** for details.

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

## CONFIGURE **mailevbills**

The **mailevbills** command emails all submeter bills in a
*nnnn*custbill*mmddyyyy*.zip file or a single
*nnnn*custbill*mmddyyyy*-*circuit*.pdf submeter bill file to the list of email
addresses found for the *circuit* in the Emporia app or website settings.  When
run on a .zip file, it also emails the corresponding PG&E PDF bill to the
`contact_email` address configured in the **evbilling.toml** file.

```
usage: mailevbills.py [-h] [-d | --debug | --no-debug] [--dry-run | --no-dry-run | --test-run ADDRESS] [--msg MSG] [-v] input_file

Send EV charging bill PDFs to charger owners via email.

positional arguments:
  input_file            Path to a .zip file containing PDF bills or a single .pdf file

options:
  -h, --help            show this help message and exit
  -d, --debug, --no-debug
                        Log debug info; default --no-debug
  --dry-run, --no-dry-run
                        Do not send emails; default --no-dry-run
  --test-run ADDRESS    Send all emails to this address instead of the charger owner(s).
  --msg MSG, --message MSG
                        Message to append to the email body; default: empty
  -v, --version         Display the version number and exit

```

Optionally, **mailevbills** can be configured for use with the *Windows File
Explorer* *Open with ...* menu to email all the bills in a
*nnnn*custbill*mmddyyyy*.zip file without needing to launch a **cmd** window and
enter a command.

To configure **mailevbills**:

1. Browse with Windows File Explorer to the folder containing the input file to
   be processed.
1. Right-click on the bill file and choose *Open with* -> *Choose another app*.
1. Scroll to the bottom and choose *More apps*.
1. Scroll to the bottom and choose *Look for another app on this PC*.
1. Browse to `C:\Users\`*`Username`*`\.local\bin`.
1. Open **mailevbills.exe**.

This will run **mailevbills** on the .zip file and add **mailevbills.exe** to the
*Choose another app* menu for future use.

# EXAMPLES

Most options are intended for testing and debugging.  After downloading a PG&E
bill named e.g. `28b5e309-580f-46c8-afa0-6e2b5ff35ec4.pdf`, the command:

```
evbilling 28b5e309-580f-46c8-afa0-6e2b5ff35ec4.pdf
```

will create a subdirectory named from the statement date found in the bill PDF,
e.g. `2026-01-08`, to which it will write all files as described earlier,
including the submeter PDF bill files to be sent to the Owners and the `.zip`
input file for **mailevbills**.  Since the name of the downloaded file is
meaningless (it is even different each time the same bill is downloaded), the
bill file is renamed the the standard form *nnnn*custbill*mmddyyyy*.pdf, e.g.
`2318custbill01082026.pdf`.

Sample **evbilling** output:

```
2026-01-13 12:47:15 - INFO - Logging into Emporia Vue AWS server ...
2026-01-13 12:47:21 - INFO - Log in OK, current Emporia Vue details for device PWS EV Energy loaded.
2026-01-13 12:47:21 - INFO - Processing \\nas0\home\git\Keith\EVBilling\Tests\Bills\2026\2318custbill01082026.pdf ...
2026-01-13 12:47:22 - WARNING - Meter 1011044609 PG&E rate period 1/1/2026 Franchise Fee Surcharge: charge not found; assuming $0.00.
2026-01-13 12:47:22 - WARNING - PG&E rate period 12/1/2025 to 12/31/2025 calculated generation credit -146.62 not equal to generation credit -146.59 shown on bill; check BEV-1 tariff UNBUNDLING OF TOTAL RATES, Generation and Bundled PCIA.
2026-01-13 12:47:22 - INFO - 2 warning(s) while processing \\nas0\home\git\Keith\EVBilling\Tests\Bills\2026\2318custbill01082026.pdf.
2026-01-13 12:47:22 - INFO - Current EV charger configuration loaded.
2026-01-13 12:47:37 - INFO - Adjustment for 01/08/2026 bill: $252.58 - $258.94 = $-6.36 (-2.5%).
2026-01-13 12:47:40 - INFO - 5 submeter bills written to "\\nas0\home\git\Keith\EVBilling\Tests\Bills\2026\2026-01-08".
2026-01-13 12:47:40 - INFO - \\nas0\home\git\Keith\EVBilling\Tests\Bills\2026\2026-01-08\2318custbill01082026.zip written to "\\nas0\home\git\Keith\EVBilling\Tests\Bills\2026\2026-01-08".
2026-01-13 12:47:40 - INFO - evbilling finished.
```

includes two WARNING messages.  The first indicates that an expected charge was
not found.  In this example, there was a rate period only one day long, and the
Franchise Fee Surcharge was omitted from the bill because it was less than
$0.00.

The second WARNING message reports a $0.03 discrepancy between the generation
credit calculated from rates found in the BEV-1 tariff and that read from the
bill.  The cause of such dsicrepancies is not known and can be ignored if small;
otherwise, check that the correct tariff and rates were used in the calculation.

A small (less than 3%) Metering Difference Adjustment indicates good accuracy:

```
2026-01-13 12:47:37 - INFO - Adjustment for 01/08/2026 bill: $252.58 - $258.94 = $-6.36 (-2.5%).
```

Generally, text is reliably extracted from searchable PDF files, but errors can
result from changes in document structure or formatting.  However, **evbilling**
auto-corrects minor discrepancies and reconciles bill amounts, making undetected
errors unlikely.  Nevertheless, comparing the plain text version of the PG&E
bill, which in this example would be named **2318custbill01082026.txt**, to the
downloaded bill is recommended to assure accuracy.

# EXPLANATION OF SUBMETER BILL LINE ITEMS

A submeter bill consists of three pages, described in the following sections.

The header of every page contains the submeter *Account* name, the *Statement
Date* from the corresponding PG&E main bill, and the *Due Date*, which is the
first day of the month after the *Statement Date*.

The footer of every page has the contact email address and the date on which
the submeter bill was produced.

## Submeter Bill Page 1

**Charger Power Rating**
: Charger power rating in kW, determined as described in *EV Charger Names and
Settings*.

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
   (Submeter Total Usage)
----------------------------
sum(All Submeter Total Usage)

X [(Main PG&E bill Total Amount Due) - sum(All submeter PG&E and CleanPowerSF charges)]
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
(Number 10kW blocks)*Months*Rate X ------------------------------------
                                   sum(All Charger Power Ratings in kW)
```

**Overage Fees**
: Fees charged for exceeding the Subscription Level kW peak power demand.
Formula:

```
(Main PG&E bill Overage Fees charge) X (Charger Power Rating in kW)
-------------------------------------------------------------------
                sum(All Charger Power Ratings in kW)
```

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
(Bundled PCIA rate $/kWh)*(Submeter Total Usage kWh)
```

**Total Generation Credit**
: Sum of the PG&E Energy Credits.

**Power Charge Indifference Adjustment**
: Addition to PG&E costs to compensate for PG&E generation assets stranded by
CleanPowerSF customers. The PCIA is determined by the "vintage" year that a
customer started to obtain power from CleanPowerSF.  Formula:

```
                           (Submeter Total Usage kWh)
(Main PG&E bill PCIA) X --------------------------------
                        (Main PG&E bill Total Usage kWh)
```

**Net Charges**
: Sum of Subscription Level charge, Subscription Overage Fees, PG&E Energy Charges,
Total Generation Credit, and Power Charge Indifference Adjustment.

**Franchise Fee Surcharge**
: Collect the fee PG&E pays to San Francisco for use of city streets to
transmit, distribute, and supply electricity.  PG&E includes both the vintage
rate from the PG&E E-FFS tariff and an SF Municipal Surcharge Adjustment in the
calculation of the main PG&E bill Franchise Fee Surcharge.  Formula:

```
                                              (Submeter Total Usage kWh)
(Main PG&E bill Franchise Fee Surcharge) X --------------------------------
                                           (Main PG&E bill Total Usage kWh)
```

**San Francisco Utility Users' Tax**
: Collect the tax PG&E pays to San Francisco for non-residential electricity
consumption.  Formula:

```
                                                    (Submeter PG&E Net Charges)
(Main PG&E bill San Francisco Utility Users' Tax) X ----------------------------
                                                    (Main bill PG&E Net Charges)
```

**SF Prop C Tax Surcharge**
: Collect the tax PG&E pays to San Francisco to fund its homelessness programs.
Formula:

```
                                           (Submeter PG&E Net Charges)
(Main PG&E bill SF Prop C Tax Surcharge) X ----------------------------
                                           (Main PG&E bill Net Charges)
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
                                                    (Submeter CleanPowerSF Net Charges)
(Main CleanPowerSF bill Local Utility Users' Tax) X ------------------------------------
                                                    (Main CleanPowerSF bill Net Charges)
```

**Energy Commission Surcharge**
: Collect the tax CleanPowerSF pays to California for consumption of electrical
energy.  Formula:

```
                                                       (Submeter CleanPowerSF Net Charges)
(Main CleanPowerSF bill Energy Commission Surcharge) X ------------------------------------
                                                       (Main CleanPowerSF bill Net Charges)
```

## CleanPowerSF Rate Changes

CleanPowerSF changes rates annually on July 1\*.  Unlike PG&E rates changes, these
are combined in a single rate period on the PG&E bill, which **evbilling**
splits into two rate periods, the first ending on June 30 and the second
beginning on July 1, assuming that the first and second rates listed for each
TOU period are the rates for the first and second rate periods, respectively.
If rates are missing due to no usage during a TOU period, **evbilling** stops
and the missing rates must be looked up from previous bills or on [CleanPowerSF
Commercial Rates, B-EV-1,
p.5](https://static1.squarespace.com/static/5a79fded4c326db242490272/t/66845b3e64535d5bbbb39dbe/1719950143549/CPSF+Commercial+Rates+2024.pdf)
and manually entered in the **sidecar** file.

\*Update the `cpsf_rate_change` setting if CleanPowerSF changes the date of its
annual rate update.

# SEE ALSO

* [Emporia Vue 3 3-PHASE Energy Monitor](https://shop.emporiaenergy.com/products/emporia-vue-3-3-phase-energy-monitor)<br>
* [Emporia Energy Help Center](https://help.emporiaenergy.com/en/)<br>
* [Emporia Vue 3 Energy Monitor](https://help.emporiaenergy.com/en/collections/9734036-energy-monitors)<br>
* [Emporia Account Login](https://web.emporiaenergy.com/login)<br>
* [PG&E Electric Schedule BEV](https://www.pge.com/tariffs/assets/pdf/tariffbook/ELEC_SCHEDS_BEV.pdf)<br>
* [Commercial Business Electric Vehicle (BEV) Rates](https://www.pge.com/tariffs/en/rate-information/electric-rates.html#accordion-a84c67dc1e-item-69d101345a)<br>
* [CleanPowerSF Commercial Rates, B-EV-1, p.5](https://static1.squarespace.com/static/5a79fded4c326db242490272/t/686427014729f246508ae08c/1751394050402/CPSF%2BCommercial%2BRates%2B2025.pdf)<br>
* [SF Franchise Fee Surcharge](https://help.pge.com/s/article/What-is-a-Franchise-Fee-Surcharge?language=en_US)<br>
* [San Francisco Utility Users' Tax (7.500%)](https://sfgov.org/lafco/sites/default/files/FileCenter/Documents/52280-4%20City%20and%20County%20of%20San%20Francisco%20Controller%E2%80%99s%20Office%20%28April%202005%29%20The%20Utility%20Users%20Tax.pdf)<br>
* [SF Prop C Tax Surcharge](https://sftreasurer.org/business/taxes-fees/homelessness-gross-receipts-tax-hgr-0)<br>
* [Energy Commission Surcharge](https://cdtfa.ca.gov/formspubs/l1020.pdf)<br>
* [PyEmVue -- Unofficial library for interacting with the Emporia Vue energy monitor](https://pypi.org/project/pyemvue/)<br>
* [TOML: A config file format for humans](https://toml.io/en/)<br>

# AUTHOR

Keith Gorlen<br>
<kgorlen@gmail.com>

# COPYRIGHT

Copyright (C) 2024, 2025 Keith Gorlen

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
