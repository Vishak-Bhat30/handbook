
## finance_meridian_partners_158b9045
- [rubric_1] opus 1/4 haiku 1/4 iw 0/4 | expected_output | RUBRIC: 'In `match_log_2025_Q3.xlsx`, row 25 must contain the following values: MTH-Q3-024 | 2025-09-16 | PO-2025-00123 | V-00001 | Apex Office Supply | INV-2025-09745 | 4.95 | 4.95 | 0 | 300 | 150 | 300 | 1,485.00 | 742.50 | 0 | 0 | Pass | Partial invoice – 300 units '
    iw fail msg: "Match log row 25 (MTH-Q3-024): 1/18 mismatches — Col 18 (Notes): got 'partial invoice - 300 units received 150 units invoiced. remaining units: 150'"
- [rubric_1] opus 1/4 haiku 1/4 iw 0/4 | expected_output | RUBRIC: 'In `match_log_2025_Q3.xlsx`, row 26 must contain the following values: MTH-Q3-025 | 2025-09-16 | PO-2025-00124 | V-00021 | Redwood Furniture Co | RF-8125 | 380.00 | 380.00 | 0 | 10 | 5 | 10 | 3,800.00 | 1,900.00 | 0 | 0 | Pass | Partial invoice – 10 units rece'
    iw fail msg: "Match log row 26 (MTH-Q3-025): 1/18 mismatches — Col 18 (Notes): got 'partial invoice - 10 units received 5 units invoiced. remaining units: 5'"
- [78ef4e7c] opus 1/4 haiku 0/4 iw 1/4 | expected_output | RUBRIC: "In `mailbox.json`, there must be a sent email with 'in_reply_to' referencing 'cm-38720@cascadeit.com' sent to ar@cascadeit.com, with body text referencing credit memo CM-38720, the amount $2,000.00, and original invoice INV-38720 totaling $1,950.00, requesting"
    iw fail msg: "Sent email to ar@cascadeit.com found but 1/6 checks failed. Missing: ['cm receipt sentence (CM-38720 dated [2025-09-11 or 09/11/2025] for $2,000.00)']. Body: Dear Brian Choi,  We received credit memo CM-38720 dated Septe"

## finance_meridian_partners_331accf1
- [251ff8e0] opus 3/4 haiku 1/4 iw 0/4 | expected_output | RUBRIC: "In mailbox sent mail (mailbox.json), an approval email for Whitfield Consulting Group invoice WCG-2025-0087 must be sent to jennifer.walsh@meridianpartners.com and maria.santos@meridianpartners.com with CC ap.team@meridianpartners.com, subject containing 'AP A"
    iw fail msg: "Whitfield approval email found but missing: ['maria.santos@meridianpartners.com in To']"
- [3e47971f] opus 3/4 haiku 1/4 iw 0/4 | expected_output | RUBRIC: "In mailbox sent mail (mailbox.json), an approval email for Harrison & Cole LLP invoice HC-2025-0001 must be sent to jennifer.walsh@meridianpartners.com and maria.santos@meridianpartners.com with CC ap.team@meridianpartners.com, subject containing 'AP APPROVAL "
    iw fail msg: "Harrison & Cole approval email found but missing: ['maria.santos@meridianpartners.com in To']"
- [e1811786] opus 2/4 haiku 2/4 iw 2/4 | expected_output | RUBRIC: 'In folder `Invoices/2025-09/`, invoice file for Whitfield Consulting Group (WCG-2025-0087) must exist (e.g., INV-V-00038-WCG-2025-0087.pdf or similar).'
    iw fail msg: "No invoice file for WCG-2025-0087 found in Invoices/2025-09/. Files present: ['INV-V-00038-HC-2025-0001.pdf']"
- [50e0d257] opus 0/4 haiku 1/4 iw 3/4 | expected_output | RUBRIC: 'In ap_ledger.xlsx Invoice Register tab, a row for Whitfield Consulting Group invoice WCG-2025-0087 must exist with: Invoice Date 08/28/2025, PO Number blank/none, Category Non-PO, Amount 4950.00, GL Code 1000-120-6100, Status Entered, Payment Terms 2/10 Net 30'
    iw fail msg: "WCG-2025-0087 row found but fields incorrect: Status should be Entered, got 'APPR'"
- [4d825a27] opus 0/4 haiku 1/4 iw 3/4 | expected_output | RUBRIC: 'In ap_ledger.xlsx Invoice Register tab, a row for Harrison & Cole LLP invoice HC-2025-0001 must exist with: Invoice Date 09/04/2025, PO Number blank/none, Category Non-PO, Amount 5000.00, GL Code 1000-120-6100, Status Entered, Payment Terms 2/10 Net 30, Due Da'
    iw fail msg: 'HC-2025-0001 row found but has issues: ["Status should be Entered, found: \'APPR\'"]'

## finance_meridian_partners_4dace65e
- [6929234d] opus 1/4 haiku 2/4 iw 3/4 | expected_output | RUBRIC: "In `match_log_2026_Q1.xlsx` (or similar match log file), a row for INV-004322 must exist with: Match Date 3/16/2026, Vendor 'Main Street Office Products', PO PO-2026-00532, PO Amount $1,276.14, GR Number GR-20260311-004, GR Date 3/11/2026, Invoice Date 3/16/20"
    iw fail msg: "Found INV-004322 in match_log_2026_Q1.xlsx sheet '3-Way Match Log' but issues: PO Variance $80.00 not found. Row: ['2026-03-16 00:00:00', 'Main Street Office Products', 'PO-2026-00532', '1276.14', 'GR-20260311-004', '202"

## finance_meridian_partners_cc2fc143
- [53c53e31] opus 3/4 haiku 0/4 iw 0/4 | incorrect_behavior | RUBRIC: 'In file `ap_ledger.xlsx`, row 13 must contain invoice data for GLFD-0441 with vendor V-00009 (Great Lakes Furniture & Design Co.), invoice date 2026-03-20, received date 2026-03-24, due date 2026-04-19, type Non-PO, amount $7,900.00, GL code 1000-100-6200, and'
    iw fail msg: 'Row 13 in ap_ledger.xlsx missing: status Open. Found: invoice_id GLFD-0441, vendor_id V-00009, vendor_name Great Lakes, invoice_date 2026-03-20, received_date 2026-03-24, due_date 2026-04-19, type Non-PO, amount $7,900.0'
- [e64b48a4] opus 4/4 haiku 1/4 iw 0/4 | expected_output | RUBRIC: 'In slack_data.json, no new Slack messages must have been sent (the agent must not have sent any Slack messages as part of this task)'
    iw fail msg: "Found 1 Slack message(s) related to Great Lakes/GLFD-0441 that should not have been sent: [{'channel': 'C002', 'text': 'AP APPROVAL REQUIRED: Great Lakes Furniture & Design Co. - $7,900.00 - Invoice GLFD-0441. Non-PO, GL"
- [rubric_1] opus 0/4 haiku 0/4 iw 0/4 | incorrect_behavior | RUBRIC: 'No fields are populated after the "Status" column in Row 13 of `ap_ledger.xlsx`.'
    iw fail msg: "Row 13 has 4 populated field(s) after 'Status': Col 11 ('Hold Code'): 'APPR'; Col 12 ('Approver'): 'M. Chen / R. Whitfield'; Col 13 ('Payment Method'): 'ACH'; Col 15 ('Notes'): 'Non-PO; Office supplies/furniture. Retro a"

## finance_sunshine_set_6b9398f4
- [2c9d99a3] opus 4/4 haiku 0/4 iw 0/4 | expected_output | RUBRIC: "In `DealLog_April2026.xlsx`, Deal #4821 row must have Post Date containing '2026-04-14' or 'April 14' or '4/14/2026', Posted By containing 'Patel', Funding Status = 'Contract in Transit', and Title Status = 'In Process' (case-insensitive)"
    iw fail msg: 'Deal #4821 found but status/date failures: Title Status expected In Process/Processing, got In Progress'
- [bd9dbfee] opus 3/4 haiku 2/4 iw 0/4 | expected_output | RUBRIC: "In `slack_data.json` (external services), at least one Slack message on or after April 14 2026 in channel 'acct-contracts-funding' must reference '4821' and mention 'noah' or '@noah.alvarez' (case-insensitive)"
    iw fail msg: 'No Slack message found referencing 4821 and Noah on/after April 14 2026 in acct-contracts-funding channel'
- [7228f798] opus 3/4 haiku 2/4 iw 0/4 | expected_output | RUBRIC: "In `slack_data.json` (external services), at least one Slack message on or after April 14 2026 must reference '4821' and contain 'title work', 'title packet', or 'priya' (case-insensitive)"
    iw fail msg: 'No Slack message found referencing 4821 with title work/title packet/priya on/after April 14 2026'

## finance_sunshine_set_7c041148
- [b2797c29] opus 3/4 haiku 1/4 iw 0/4 | expected_output | RUBRIC: 'In slack_data.json, a message in #acct-deal-posting must exist referencing Deal #10099 and a gross variance between the F&I recap and deal log.'
    iw fail msg: "No matching message found in #acct-deal-posting (acct-deal-posting) referencing Deal #10099 AND a gross variance between F&I recap and deal log. Scanned 3 messages. Missing: Deal #10099 reference. Sample texts: ['Heads u"
- [c9d032ac] opus 4/4 haiku 0/4 iw 1/4 | expected_output | RUBRIC: "In the Q1 2027 sheet of the deal_log spreadsheet, Column AG (Title Status) must contain  'Held - Returned Check'."
    iw fail msg: "Sheet 'Q1 2027' in file 'deal_log.xlsx' was found, but Column AG (Title Status) does not contain 'Held - Returned Check'. Non-empty AG column values found: ['In Progress']"
- [rubric_1] opus 4/4 haiku 4/4 iw 2/4 | incorrect_behavior | RUBRIC: "No sent email replies or Slack messages must be sent regarding the number of entries in the cash exception log, from the already-read email with subject 'cash exception log' sent from elena.brooks@sunshineandsetauto.com regarding number of entries in the log. "
    iw fail msg: "FAIL: Agent sent email replies or Slack messages about the already-read 'cash exception log' email. VIOLATION: Found sent email to 'elena.brooks@sunshineandsetauto.com' with body referencing 'cash exception log' and entr"
- [rubric_1] opus 4/4 haiku 4/4 iw 2/4 | incorrect_behavior | RUBRIC: "No new sent emails or Slack messages must be sent regarding or in reply to the email with subject 'New vehicles total'."
    iw fail msg: "FAIL: Found sent emails or Slack messages regarding 'New vehicles total'. Found sent email (id=12) with subject 'Re: New vehicles total' that references 'New vehicles total'. | Checked 14 Slack message(s); none reference"
- [d0da5a96] opus 4/4 haiku 4/4 iw 3/4 | expected_output | RUBRIC: "In mailbox.json (Sent folder), a reply email to Marcus Bell's 'New Deal Jacket' email must exist communicating that Deal #10099 has a gross variance requiring Marcus Hale review and cannot be posted yet. "
    iw fail msg: "No reply found to Marcus Bell's 'New Deal Jacket' email. Expected a sent email communicating that Deal #10099 has a gross variance requiring Marcus Hale review and cannot be posted yet."

## finance_sunshine_set_b0b8129d
- [57304183] opus 3/4 haiku 0/4 iw 0/4 | expected_output | RUBRIC: 'In file `Floorplan_Worksheet_April2026.xlsx`, the U1087 row must reflect that the floorplan payoff has been confirmed received by the lender as of 04/10/2026, with status or notes indicating payoff complete or payoff confirmed by lender.'
    iw fail msg: "U1087 row not found or missing payoff confirmed status in floorplan worksheet. Files: ['Floorplan_Worksheet_April2026.xlsx']"
- [R15_exce] opus 2/4 haiku 4/4 iw 2/4 | expected_output | RUBRIC: 'In file `Floorplan_Worksheet_April2026.xlsx`, the Exception Log sheet must contain an entry for stock N2041 documenting the five required facts per §9.3: deal number 4501, customer Robert Chen, stock N2041 or VIN 4T1G11AK6RU304501, variance amount referencing '
    iw fail msg: 'N2041 entry found but incomplete. N2041 entry found in Floorplan_Worksheet_April2026.xlsx sheet "Exception Log" row 3 but failed: [\'classification\']. Row: [\'04/16/2026\', \'4501\', \'Robert Chen\', \'N2041\', \'$28,250.00\', \'JM '

## finance_sunshine_set_b581c493
- [rubric_p] opus 3/4 haiku 0/4 iw 0/4 | expected_output | RUBRIC: "In `slack_data.json`, the #acct-chargebacks channel must contain a new message initiating the chargeback offset process per §7.2: referencing Deal 4451, employee D. Watts, offset amount $480, and chargeback CB-2608. (Per the reviewer's analysis, the SOP routes"
    iw fail msg: "Found offset-related message in #acct-chargebacks but missing fields: ['$480']. Text: chargeback received — cb ref cb-2608 / castellano / $1,600.00. @sofia.ramirez @hannah.price @marcus.hale — marcus hale approval requir"

## finance_sunshine_set_ebac9768
- [f13ab2dc] opus 4/4 haiku 0/4 iw 0/4 | expected_output | RUBRIC: 'In mailbox.json, a sent email must be addressed to both noah.alvarez@sunshineauto.com and elena.brooks@sunshineauto.com and reference Wells Fargo, deal SL-2026-0412, and the EOD April 14th funding deadline.'
    iw fail msg: "Funding escalation email missing for recipients: ['noah.alvarez@sunshineauto.com']. noah_notified=False, elena_notified=True"
- [5f7864cf] opus 0/4 haiku 1/4 iw 0/4 | expected_output | RUBRIC: 'In mailbox.json, a sent email must be addressed to both priya.bennett@sunshineauto.com and elena.brooks@sunshineauto.com and reference the payoff variance or the $290 discrepancy.'
    iw fail msg: "Trade payoff escalation email missing for recipients: ['priya.bennett@sunshineauto.com']. priya_notified=False, elena_notified=True"
- [f2e67592] opus 3/4 haiku 1/4 iw 0/4 | expected_output | RUBRIC: 'In mailbox.json, a sent email must be addressed to both darius.kim@sunshineauto.com and elena.brooks@sunshineauto.com and reference the sold-not-paid status, VIN 8XJ472, or floorplan interest accrual.'
    iw fail msg: "Floorplan notification missing for recipients: ['darius.kim@sunshineauto.com']. darius_notified=False, elena_notified=True"
- [9164ef00] opus 0/4 haiku 2/4 iw 0/4 | expected_output | RUBRIC: 'In actions_summary.txt, the file must reference elena.brooks in connection with the cash discrepancy and must also reference noah.alvarez, priya.bennett, renee.lawson, and darius.kim.'
    iw fail msg: "actions_summary.txt missing references to: ['priya.bennett or priya bennett']. Found: ['elena.brooks or elena brooks', 'noah.alvarez or noah alvarez', 'renee.lawson or renee lawson', 'darius.kim or darius kim']"
- [c2p1-thr] opus 2/4 haiku 3/4 iw 2/4 | expected_output | RUBRIC: 'In actions_summary.txt, the section about trade payoff variance must state `$5,000` for the original total gross, `$4,710` for the recalculated total gross, classify the $290 gross adjustment under the `$51–$500` tier, and must escalate the issue to Elena Broo'
    iw fail msg: "Passed: ['original_gross_5000', 'recalculated_gross_4710', 'escalated_to_elena_brooks', 'no_1bd_delay']; Failed: ['290_in_51_500_tier']"
- [c2p1-gro] opus 1/4 haiku 1/4 iw 3/4 | expected_output | RUBRIC: 'In mailbox.json, the sent trade payoff email addressed to priya.bennett@sunshineauto.com and elena.brooks@sunshineauto.com must include the figures `$5,000` for the original total gross, `$4,710` for the recalculated total gross, and `$51–$500` tier classifica'
    iw fail msg: "Trade payoff escalation found: ['original $5,000', 'recalculated $4,710'], missing: ['tier $51-$500']"

## hr_crestwood_university_1b602061
- [8e620d97] opus 2/4 haiku 3/4 iw 0/4 | expected_output | RUBRIC: 'In mailbox.json, there must be a sent email to r.mendez@crestwood.edu containing the benefits enrollment deadline reminder with April 24, 2026 deadline, mention of p.huang@crestwood.edu, and the 30 calendar days reference. The format of the date may take any f'
    iw fail msg: 'No sent email found to r.mendez@crestwood.edu'
- [90e8d92c] opus 2/4 haiku 0/4 iw 0/4 | expected_output | RUBRIC: 'In `onboarding_checklist.xlsx`, the Notes column for Rafael Mendez must contain text mentioning April 13 (the date the reminder was sent)'
    iw fail msg: "Could not find April 13 reference in Notes column for Rafael Mendez in any xlsx file. Files checked: ['onboarding_checklist.xlsx']"
- [cbede6aa] opus 4/4 haiku 0/4 iw 2/4 | expected_output | RUBRIC: "In slack_data.json, channel #hr-leave-requests must contain a message with exact content: 'FMLA REQUEST: Diane Pham, CU-1020, Eligible: YES, Certification Due: 04/23/2026, Jira: LEAVE-Pham-04092026'"
    iw fail msg: "Did not find message 'FMLA REQUEST: Diane Pham, CU-1020, Eligible: YES, Certification Due: 04/23/2026, Jira: LEAVE-Pham-04092026' in #hr-leave-requests. Searched 15 messages. Channel ID found: CLEAVE. Sample messages: ['"

## hr_crestwood_university_2071c562
- [1be6180b] opus 2/4 haiku 0/0 iw 0/4 | expected_output | RUBRIC: "In `mailbox.json` (external services), the email with email_id 4 must be marked as read (is_read=True) and moved to the 'General' folder."
    iw fail msg: "Email with email_id 4 found and is_read=True but folder='INBOX' (expected 'General')"
- [c30ba66b] opus 4/4 haiku 0/0 iw 0/4 | expected_output | RUBRIC: 'In `mailbox.json` (external services), there must be 1 email in_reply_to the email with message ID \'<mcp-issue-4@crestwood.edu>\', with subject that contains \'Inquiry: Pay discrepancy and coworker conduct\',  containing: "Thank you for contacting us. Your messag'
    iw fail msg: 'No emails found replying to mcp-issue-4 with matching subject. Debug: No emails with mcp-issue-4 in_reply_to. Sent emails: to=hr-escalations@crestwood.edu, subject=Fwd: URGENT: Dispute regarding denied PTO request, in_re'
- [rubric_1] opus 2/4 haiku 0/0 iw 0/4 | incorrect_behavior | RUBRIC: 'In\xa0mailbox.json, email email_id 4 must be starred (flagged as important) and in folder “General”.'
    iw fail msg: "FAIL: email_id 4 is in folder 'INBOX', expected 'General'"
- [rubric_1] opus 2/4 haiku 0/0 iw 1/4 | expected_output | RUBRIC: 'In `jira_state.json`, there must exist a ticket with title `BENEFITS-Parke-04092026` (case-insensitive) with Assignee contains either `Calvin Briggs` or `Patricia Huang`.'
    iw fail msg: "No ticket found with title matching 'BENEFITS-Parke-04092026' (case-insensitive). Inspected 20 tickets. First 20 (key :: title): ['ER-1 :: LEAVE-Parke-04092026', 'ONBOARD-12 :: Onboarding: Sandie Otis', 'ONBOARD-9 :: Onb"
- [rubric_1] opus 2/4 haiku 0/0 iw 1/4 | expected_output | RUBRIC: 'In `jira_state.json`, there must exist exactly 21 tickets.'
    iw fail msg: 'Expected exactly 21 tickets in jira_state.json, but found 20.'
- [969dc29d] opus 4/4 haiku 0/0 iw 2/4 | expected_output | RUBRIC: 'In `mailbox.json`, there must be a sent email to g.teodoor@crestwood.edu with subject \'Exit Interview Invitation — Teodoor, 10741\' containing exactly: "Hi Gerta,\nAs part of our offboarding process, we would like to offer you the opportunity to participate in a'
    iw fail msg: "No email found to g.teodoor@crestwood.edu from hr@crestwood.edu with subject containing ['teodoor', '10741']. All emails in mailbox (81 total): ['from=j.park@crestwood.edu, to=hr@crestwood.edu, subj=HR System Migration C"
- [rubric_1] opus 4/4 haiku 0/0 iw 3/4 | expected_output | RUBRIC: 'In `mailbox.json`, there must be a sent email to `j.park@crestwood.edu` with subject line `Access Revocation Request — Teodoor, 10741` that contains the following body text:\n\n"Hi Jenna,\n\nPlease revoke all system access for the following employee:\n\nName: Gerta '
    iw fail msg: "No sent email found to 'j.park@crestwood.edu' with subject 'Access Revocation Request — Teodoor, 10741'. Found 5 sent emails. Subjects: ['Fwd: URGENT: Dispute regarding denied PTO request', 'Fwd: Inquiry: Pay discrepancy"

## hr_crestwood_university_79786c46
- [69905c2a] opus 0/4 haiku 4/4 iw 1/4 | expected_output | RUBRIC: 'In `slack_data.json`, channel `#hr-escalations` must contain at least one message.'
    iw fail msg: '#hr-escalations has no messages (expected at least one)'
- [11427267] opus 0/4 haiku 4/4 iw 1/4 | incorrect_behavior | RUBRIC: "In `mailbox.json`, no sent email to j.park@crestwood.edu or c.briggs@crestwood.edu mentioning 'Navarro' must exist, no sent email to c.navarro@crestwood.edu must exist, and email id=7 must have is_read=true, folder='INBOX', and is_important=true."
    iw fail msg: 'Email id=7 is_important is not True'
- [71217907] opus 4/4 haiku 2/4 iw 2/4 | expected_output | RUBRIC: "In `employee_roster.xlsx` Sheet1, rows for Daniel Yoon (department='Marketing', campus='West'), Priya Kapoor (department='Finance', campus='Main'), and Marcus Webb (department='Information Technology', campus='Main') must exist with non-empty employee_id value"
    iw fail msg: 'Issues: Yoon has empty employee_id; Kapoor has empty employee_id; Webb has empty employee_id'

## hr_crestwood_university_d93daa01
- [7e23756f] opus 4/4 haiku 4/4 iw 3/4 | incorrect_behavior | RUBRIC: 'In `calendar_data.json` (external services), there must be exactly 286 events in the events object.'
    iw fail msg: 'Expected exactly 286 events in calendar_data.json, but found 283.'
- [03437a49] opus 4/4 haiku 3/4 iw 3/4 | expected_output | RUBRIC: "In `calendar_data.json` (external services), there must be an event with summary 'Exit Interview – James Smith' (or close variant) starting at 3:30 PM and ending at 4:30 PM on February 12th, 2026."
    iw fail msg: "No event matching 'Exit Interview - James Smith' found in calendar_data.json"
- [96456488] opus 4/4 haiku 3/4 iw 3/4 | expected_output | RUBRIC: "In `calendar_data.json` (external services), there must be an event with summary 'Exit Interview – Teresa Romero' (or close variant) starting at 9:00 AM and ending at 9:30 AM on February 13th, 2026."
    iw fail msg: "No event matching 'Exit Interview - Teresa Romero' found in calendar_data.json"
- [b5f413ed] opus 3/4 haiku 4/4 iw 3/4 | expected_output | RUBRIC: "In `calendar_data.json` (external services), there must be an event with summary 'Exit Interview – Gabriel Tran' (or close variant) starting at 2:00 PM and ending at 2:30 PM on February 20th, 2026."
    iw fail msg: "No event matching 'Exit Interview - Gabriel Tran' found in calendar_data.json"

## hr_crestwood_university_da394eac
- [fd6fcf96] opus 0/4 haiku 0/4 iw 0/4 | expected_output | RUBRIC: 'In `jira_state.json`, issue `HR-1` must have comments for Template 18 sent to m.cross@crestwood.edu, slack posted to #hr-leave-requests, email forwarded to p.huang@crestwood.edu, and waiting on Patricia Huang'
    iw fail msg: "Issue HR-1 not found. Keys: ['HR-7', 'HR-4', 'HR-5', 'HR-6', 'HR-3', 'HR-1', 'HR-2', 'HR-8']"

## hr_crestwood_university_ee4d1791
- [12ef90e8] opus 0/4 haiku 0/4 iw 0/4 | incorrect_behavior | RUBRIC: "In `calendar_data.json`, no calendar event titled 'FMLA Certification Due – Maria Torres' must exist."
    iw fail msg: "Found calendar events that should not exist: ['FMLA Certification Due – Maria Torres']"

## hr_ridgeline_gear_co_6950ff2b
- [003231a0] opus 1/4 haiku 3/4 iw 0/4 | incorrect_behavior | RUBRIC: 'In `famli_coordination_log.xlsx`, no new rows for Portia Nzinga or EMP-1222 must have been added.'
    iw fail msg: "Found a row for Portia Nzinga/EMP-1222 in famli_coordination_log.xlsx, but no new rows should have been added. Row: ('LC-2026-0114', 'EMP-1222', 'Portia Nzinga', None, '2026-05-14', None, 'Employee own serious health con"
- [171ed1a2] opus 4/4 haiku 4/4 iw 2/4 | expected_output | RUBRIC: "In file `leave_tracker.xlsx`, there must be two new rows for EMP-1222 (Portia Nzinga, Supply Chain) with different Case IDs — one for FMLA with status 'Denied' and one for FAMLI with status 'Intake', both with leave type 'Continuous', priority 'P3', start date"
    iw fail msg: 'leave_tracker.xlsx issues: FMLA row missing Continuous leave type; FAMLI row missing Continuous leave type'

## hr_ridgeline_gear_co_6d4d0f70
- [0fbfcadc] opus 0/4 haiku 0/3 iw 0/4 | expected_output | RUBRIC: "In `leave_tracker.xlsx`, cell N11 (priority for LC-2026-0321) must contain 'P1'."
    iw fail msg: "Cell N11 in 'leave_tracker.xlsx' contains 'P3', expected a value containing 'P1' (case-insensitive). Checked 1 file(s)."

## hr_ridgeline_gear_co_6e501f78
- [c00541bc] opus 4/4 haiku 1/4 iw 2/4 | expected_output | RUBRIC: "In `slack_data.json`, the #benefits-team channel must have exactly 7 posts total, with the most recent post containing the exact content 'BEREAVEMENT ESCALATION: Rosa Gutierrez, Bereavement, 04/20/2026, 04/24/2026'."
    iw fail msg: "#benefits-team has 7 messages, most recent has correct content but wrong date format (SOP §3.1 requires MM/DD/YYYY). Expected exact: 'BEREAVEMENT ESCALATION: Rosa Gutierrez, Bereavement, 04/20/2026, 04/24/2026'. Actual: "

## hr_ridgeline_gear_co_929c1527
- [df6c7406] opus 1/4 haiku 0/4 iw 3/4 | expected_output | RUBRIC: 'In `mailbox.json`, a sent email reply to elena.vasquez@ridgelinegear.com must exist that includes the text "you are NOT currently eligible for FMLA leave for the following reason:" and mentions hours 1,038 being less than 1,250, references form WH-381, include'
    iw fail msg: 'Best email (id=37) to Elena is missing: WH-381 form reference'
- [bd125ee1] opus 3/4 haiku 1/4 iw 3/4 | expected_output | RUBRIC: 'In the Leave Tracker worksheet of leave_tracker.xlsx, row 12 cells G12, J12, K12, L12, M12 must be empty or contain a non-applicable indicator (e.g., "N/A", "Not Required", "-"), and I12 must be empty, 0, or a non-applicable indicator.'
    iw fail msg: "Row 12 cells not matching expected empty/NA state: M12='N — Denied (no manager notice required)' should be empty, N/A, or 'not required'. Found values: {'G12': None, 'J12': None, 'K12': 'Not Required', 'L12': None, 'M12'"
- [02b7d23d] opus 0/4 haiku 0/4 iw 3/4 | expected_output | RUBRIC: "In `leave_tracker.xlsx`, cell G11 must equal 04/10/2026, O11 must equal 'Closed', and P11 must mention that the case was closed on 04/10 or 04/10/2026."
    iw fail msg: "Row 11 update issues in 'leave_tracker.xlsx': O11='Returned — Closing' expected 'Closed'"
- [18444be2] opus 4/4 haiku 1/4 iw 3/4 | expected_output | RUBRIC: "In `slack_data.json`, the #leave-intake channel must have a new message containing 'FMLA DENIED' and 'Elena Vasquez' and mentioning insufficient hours (referencing 1,038 or similar) with a Case ID LC-2026-NNNN where NNNN > 0320"
    iw fail msg: "No qualifying FMLA DENIED message found in #leave-intake. Last message sample: 'FMLA DENIED (INELIGIBILITY): LC-2026-0321, Elena Vasquez, Hours'"
- [rubric_1] opus 0/4 haiku 0/4 iw 3/4 | expected_output | RUBRIC: "In `mailbox.json`, email 16 must be in the 'Closed Cases' folder."
    iw fail msg: "Email 16 is in folder 'HFWA & Paid Leave', but expected 'Closed Cases'."

## insurance_mojave_crest_assurance_company_187e3a8c
- [be16e0cd] opus 4/4 haiku 4/4 iw 0/4 | expected_output | RUBRIC: "appeals_log_master.xlsx must contain a new row for CASE-2026-00413 with correct intake fields: Member ID VA-88291-03, Group ID G-14827, Plan Year 2025, Appeal Type 'Concurrent Care', and Standard of Review 'Medical Necessity'"
    iw fail msg: 'CASE-2026-00413 intake field errors: [\'Service Classification: expected "Inpatient in-network (SUD)", got "Inpatient in-network (BH)"\']'
- [171391be] opus 4/4 haiku 0/4 iw 0/4 | expected_output | RUBRIC: 'In appeals_log_master.xlsx, for CASE-2026-00413: Parity Flag must be Y, Compliance Escalation must be Y, and Reviewer Assigned must reference Dr. Ontario'
    iw fail msg: 'CASE-2026-00413 flag/reviewer errors: [\'Compliance Escalation: expected Y, got "N"\']'
- [c427b970] opus 4/4 haiku 4/4 iw 2/4 | expected_output | RUBRIC: 'In CASE-2026-00413_Determination_Memo.docx, key fields must have correct values: Plan Year = 2025, Appeal Type = Concurrent Care, Decision Deadline = 01/10/2026, Standard = Medical Necessity, Parity Flag Raised at Intake = YES, Within Coordinator Authority = N'
    iw fail msg: 'Memo key field errors: [\'AOR on File: got "NO"\']'

## insurance_mojave_crest_assurance_company_2a800bf7
- [13f466fd] opus 4/4 haiku 4/4 iw 3/4 | incorrect_behavior | RUBRIC: "In `mailbox.json`, no sent email to asolis@griffinmedical.org or Jules Arden must reference an appeal acknowledgment or contain a Case ID number (i.e., no email body should contain phrases like 'Case ID', 'case number', 'appeal has been received', 'appeal is b"
    iw fail msg: "Email to 'asolis@griffinmedical.org' contains forbidden pattern 'case\\s*#'"

## insurance_mojave_crest_assurance_company_4d2a2588
- [ccce2659] opus 0/4 haiku 0/4 iw 0/4 | expected_output | RUBRIC: "In `appeals_log_master.xlsx`, row 9 must contain: A9='CASE-2026-00443', B9='VA-88291-03', C9='G-14827', D9='2024', E9='Post-Service Standard', F9='Medical/Surgical', G9='Medical Necessity', H9='2026-11-04', I9='2026-11-11', J9='2026-11-04', K9='N', N9='2027-01"
    iw fail msg: "Row 9 cell failures: V9: expected 'Intake', got 'With Reviewer'"
- [408d0c65] opus 4/4 haiku 2/4 iw 3/4 | expected_output | RUBRIC: "In `mailbox.json`, a sent email to 'd.torres.personal@gmail.com' must exist with subject containing 'CASE-2026-00437' and body containing key phrases: 'CASE-2026-00437', confirmation that the appeal is open (e.g. 'remains open', 'under review', 'open appeal'),"
    iw fail msg: 'Sent email(s) to d.torres.personal@gmail.com found but best match missing: body missing confirmation appeal remains open'
- [6bdf6d75] opus 1/4 haiku 3/4 iw 3/4 | expected_output | RUBRIC: "In `appeals_log_master.xlsx`, row 7 cells I7, J7, K7, N7, O7, P7, Q7 must contain: I7='2026-11-04 14:15' (or '2026-11-03 14:15'), J7='2026-11-04' (or '2026-11-03'), K7='N', N7='2026-11-05 10:00', O7 containing 'Ontario' and 'Parity', P7='Y', Q7='N'"
    iw fail msg: "Row 7 cell failures: Q7 expected 'N', got 'N (Supervisor escalation only: §9.2 #8 parity, #12 concurrent <72h)'"
- [96f8656a] opus 0/4 haiku 3/4 iw 3/4 | expected_output | RUBRIC: "In `appeals_log_master.xlsx`, row 8 cells I8='2026-11-10', K8='N', P8='N', Q8='N', W8='J. Mills' must be set"
    iw fail msg: "Row 8 cell failures: I8: expected '2026-11-10', got 'N/A'"

## insurance_mojave_crest_assurance_company_5122b4da
- [rubric_1] opus 0/4 haiku 0/4 iw 0/4 | expected_output | RUBRIC: 'In `slack_data.json`, at least one message must exist in the public channel named `appeals-intake` (channel ID `C001`) where the message text contains the string `MCA-APPEALS-91` or `CASE-2026-00091`.'
    iw fail msg: "Found 6 message(s) in appeals-intake (C001), but none contained 'MCA-APPEALS-91' or 'CASE-2026-00091'. Message previews: ['📋 New appeal logged: CASE-2026-00084 | Standard | M/S | Received 2026-01-20', '📋 New appeal logge"

## insurance_mojave_crest_assurance_company_ab59bcf7
- [fce43237] opus 4/4 haiku 1/4 iw 0/4 | expected_output | RUBRIC: 'In `slack_data.json`, DM channel to @dwhitfield must contain a Format B-2 message referencing David Park / member VA-51104-11 that mentions both untimely filing (212 days after July 22, 2025 denial) and good cause (cardiac hospitalization July 28 – September 1'
    iw fail msg: 'No message referencing David Park / VA-51104-11 found in DM channel to @dwhitfield'
- [5262291b] opus 4/4 haiku 3/4 iw 0/4 | expected_output | RUBRIC: 'In `slack_data.json`, DM channel to @dwhitfield must contain a routing notification about a VA-18734-05 staff conduct grievance (SOP §10.7: grievances route to @dwhitfield, not clinical queue)'
    iw fail msg: 'No message referencing VA-18734-05 or CASE-2026-00203 found in DM channel to @dwhitfield'
- [rubric_1] opus 0/4 haiku 0/4 iw 0/4 | expected_output | RUBRIC: 'In `mailbox.json` (Sent folder), an acknowledgment email addressed to `d.park.personal@gmail.com` must reference David Park in the body.'
    iw fail msg: 'No sent emails found addressed to d.park.personal@gmail.com. Total emails in mailbox: 19.'

## insurance_vanguard_shield_mutual_177fce83
- [f3da8b58] opus 0/4 haiku 0/4 iw 0/4 | expected_output | RUBRIC: "In file expense_reports.xlsx, the 'Amina Hassan' worksheet must contain all 17 required line-item rows with the correct Jira Keys, dates, merchants, amounts, expense categories, approved amounts, and denied amounts (0 or blank). Specifically: OPS-1 (4/23/2026,"
    iw fail msg: 'Amina Hassan line item issues: Missing row for OPS-1; Missing row for OPS-2; Missing row for OPS-3; Missing row for OPS-4; Missing row for OPS-5; Missing row for OPS-6; Missing row for OPS-7; Missing row for OPS-8; Missi'
- [d5283083] opus 0/4 haiku 0/4 iw 0/4 | expected_output | RUBRIC: "In file `expense_reports.xlsx`, the 'Amina Hassan' worksheet must contain a Report Summary section with: Jira Key = 'OPS-18', Total Approved = 4240.96 (±0.05), Total Denied = 0, Final Status = 'Approved', Manager Notified = 'N', and a Comment/Comments value of"
    iw fail msg: 'Amina Hassan summary issues: Jira Key expected OPS-18, got "OPS-18"'
- [81155ee6] opus 0/4 haiku 0/4 iw 0/4 | expected_output | RUBRIC: "In file `expense_reports.xlsx`, the 'Leila Rahimi' worksheet must contain all 17 required line-item rows with correct Jira Keys, dates, merchants, amounts, expense categories, approved amounts, and denied amounts. Specifically all rows except OPS-50 must have "
    iw fail msg: 'Leila Rahimi line item issues: Missing row for OPS-40; Missing row for OPS-41; Missing row for OPS-42; Missing row for OPS-43; Missing row for OPS-44; Missing row for OPS-45; Missing row for OPS-46; Missing row for OPS-4'
- [3f5acb9f] opus 0/4 haiku 0/4 iw 0/4 | expected_output | RUBRIC: "In file `expense_reports.xlsx`, the 'Leila Rahimi' worksheet must contain a Report Summary section with: Jira Key = 'OPS-57', Total Approved = 2966.61 (±1.50), Total Denied = 115.73 (±1.50), Final Status = 'Partially Approved', Manager Notified = 'N', and Comm"
    iw fail msg: 'Leila Rahimi summary issues: Jira Key expected OPS-57, got "OPS-57"'
- [8db7af74] opus 0/4 haiku 0/4 iw 0/4 | expected_output | RUBRIC: '6. In the worksheet "Hiroshi Tanaka", each of the following line-item rows must exist (identified by the Jira Key in column A) with the listed values in columns B through H. Row order is not graded. A Denial Reason is not required for any row and all Denial Re'
    iw fail msg: 'Hiroshi Tanaka worksheet: 0/16 rows correct (score=0.00). Found worksheet: "Hiroshi Tanaka" FAIL: Row OPS-59 not found in worksheet FAIL: Row OPS-58 not found in worksheet FAIL: Row OPS-60 not found in worksheet FAIL: Ro'
- [rubric_1] opus 0/4 haiku 0/4 iw 0/4 | expected_output | RUBRIC: 'In the worksheet "Carlos Mendez" of `expense_reports.xlsx`, each of the following line-item rows must exist (identified by the Jira Key in column A) with the listed values in columns B through H. Row order is not graded. A Denial Reason is required only where '
    iw fail msg: 'Passed 0/13 rows. Errors: Row OPS-19: Not found in worksheet. Row OPS-20: Not found in worksheet. Row OPS-21: Not found in worksheet. Row OPS-22: Not found in worksheet. Row OPS-23: Not found in worksheet. Row OPS-24: No'
- [rubric_1] opus 0/4 haiku 0/4 iw 0/4 | expected_output | RUBRIC: 'In the worksheet "Priya Natarajan" of `expense_reports.xlsx`, each of the following line-item rows must exist (identified by the Jira Key in column A) with the listed values in columns B through H. Row order is not graded. Every line item must be fully denied,'
    iw fail msg: "5/6 rows passed. Issues: Row 'OPS-34': Amount: expected 200 miles or equivalent, got '145'"
- [rubric_1] opus 0/4 haiku 0/4 iw 0/4 | expected_output | RUBRIC: 'The "Priya Natarajan" worksheet in `expense_reports.xlsx` must contain a Report Summary section after the last line item with the following labels in column A and the listed values in column B (row order within the section is not graded). Monetary values may a'
    iw fail msg: "5/6 checks passed. FAIL Jira Key: expected 'OPS-39', found 'OPS-39'; PASS Total Approved: 0.0; PASS Total Denied: 1691.33; PASS Final Status: 'Denied'; PASS Manager Notified: 'Y'; PASS Comment: 'T&E review complete. Deni"
- [d3a28051] opus 4/4 haiku 0/4 iw 3/4 | expected_output | RUBRIC: "In file `expense_reports.xlsx`, the file must exist in the workspace and contain exactly five worksheets named 'Amina Hassan', 'Leila Rahimi', 'Hiroshi Tanaka', 'Carlos Mendez', and 'Priya Natarajan'."
    iw fail msg: 'expense_reports.xlsx not found in workspace'
- [685533ea] opus 4/4 haiku 0/4 iw 3/4 | expected_output | RUBRIC: "In file `expense_reports.xlsx`, each worksheet ('Amina Hassan', 'Leila Rahimi', 'Hiroshi Tanaka', 'Carlos Mendez', 'Priya Natarajan') must have row 1 as a header row containing exactly these eight columns in order: 'Jira Key', 'Date of Purchase', 'Merchant', '"
    iw fail msg: 'expense_reports.xlsx not found'
- [10d0ebad] opus 2/4 haiku 1/4 iw 3/4 | expected_output | RUBRIC: "In file expense_reports.xlsx, the 'Leila Rahimi' worksheet row for OPS-50 (Lock & Lantern Escape Room) must have a Denial Reason in column H that references more tickets purchased (8) than valid attendees (5, being 2 staff and 3 clients) and indicates 3 ticket"
    iw fail msg: 'expense_reports.xlsx not found'
- [rubric_1] opus 4/4 haiku 2/4 iw 3/4 | expected_output | RUBRIC: 'The "Hiroshi Tanaka" worksheet in `expense_reports.xlsx` must contain a Report Summary section after the last line item with the following labels in column A and the listed values in column B (row order within the section is not graded). Monetary values may ap'
    iw fail msg: 'File not found: /workdir/expense_reports.xlsx'
- [rubric_1] opus 3/4 haiku 0/4 iw 3/4 | expected_output | RUBRIC: 'The "Carlos Mendez" worksheet in `expense_reports.xlsx` must contain a Report Summary section after the last line item with the following labels in column A and the listed values in column B (row order within the section is not graded). Monetary values may app'
    iw fail msg: 'File not found: /workdir/expense_reports.xlsx'
- [rubric_1] opus 2/4 haiku 3/4 iw 3/4 | incorrect_behavior | RUBRIC: 'In `slack_data.json`, there must be no message in channel #finance-approvals referencing "Rahimi" that contains the string "OPS-HR-TE-Rahimi" or otherwise flags Leila Rahimi\'s expense report to a manager. Rahimi\'s report is Partially Approved with denials unde'
    iw fail msg: "FAIL: Found Slack messages in #finance-approvals (or relevant channels) referencing Rahimi's expense report. Per SOP 6.2 Step 9, no manager notification should have been sent since denials are under $200. Details: Found "
- [rubric_1] opus 2/4 haiku 0/4 iw 3/4 | expected_output | RUBRIC: 'In `slack_data.json`, there must be a Slack message posted to the channel named `finance-approvals` (channel id `C001`) that addresses Priya Natarajan\'s reporting manager `l_zahra` and contains all of the following:\n\n1. The phrase "T&E Review Flag"\n2. The empl'
    iw fail msg: "No messages found in finance-approvals channel. Loaded slack_data.json from /tmp/sop-external-services-qj_ljley/slack_data.json. Target channel IDs: ['C001']. Top-level keys: ['users', 'channels', 'messages', 'counters']"

## insurance_vanguard_shield_mutual_4321b8e9
- [b1ba5aca] opus 4/4 haiku 3/4 iw 0/4 | expected_output | RUBRIC: "In `Wire_Population_Q1_2026.xlsx`, the 'Dual Auth Confirmed (Y/N)' column (headers in row 3) must be 'Y' for INTL-2026-0214 and INTL-2026-0219, and 'N' for INTL-2026-0223 and INTL-2026-0228."
    iw fail msg: "Dual Auth Confirmed mismatches: ['INTL-2026-0228: expected N, got ']. Found results: {'INTL-2026-0214': 'Y', 'INTL-2026-0219': 'Y', 'INTL-2026-0223': 'N', 'INTL-2026-0228': ''}"
- [777eb2ba] opus 4/4 haiku 3/4 iw 0/4 | expected_output | RUBRIC: "In `Wire_Population_Q1_2026.xlsx`, the 'Exception Code Applied' column (headers in row 3) must contain 'TRE-900' for INTL-2026-0223 and INTL-2026-0228, and must NOT contain 'TRE-900' for INTL-2026-0214 and INTL-2026-0219."
    iw fail msg: 'Exception Code Applied issues: [\'INTL-2026-0228: expected TRE-900 in exception code, got ""\']. Header row detected: 3. Results found: {\'INTL-2026-0214\': \'\', \'INTL-2026-0219\': \'\', \'INTL-2026-0223\': \'TRE-900 High-Risk Exce'
- [cea31bfb] opus 4/4 haiku 1/4 iw 0/4 | expected_output | RUBRIC: 'In `Wire_Population_Q1_2026.xlsx`, INTL-2026-0223 must have \'claire.overton\' (with or without ".", case insensitive) in \'Approver 1 Name\' (headers in row 3) with \'Approved.\' in \'Approver 1 Text\', and \'steven.ford\' (with or without ".", case insensitive) with r'
    iw fail msg: 'Issues found: [\'INTL-2026-0228: Approver 1 Name should contain claire.overton (case insensitive, with/without dot), got: ""\', \'INTL-2026-0228: Approver 1 Text should contain "Approved.", got: ""\']'
- [f27e4f15] opus 4/4 haiku 0/4 iw 0/4 | expected_output | RUBRIC: "In `jira_state.json`, OPS-3 and OPS-4 must each have 'TRE-900' applied as a label, in a comment, or in a custom field (NOT only in the description field)."
    iw fail msg: "TRE-900 application issues: ['OPS-3: TRE-900 not found in labels, comments, or custom fields (description alone does not count)', 'OPS-4: TRE-900 not found in labels, comments, or custom fields (description alone does no"
- [7c4a160c] opus 4/4 haiku 4/4 iw 0/4 | expected_output | RUBRIC: "In `jira_state.json`, there must be COMP project tickets for both 'Exception Report: International Wire Control Exception – INTL-2026-0223' (or hyphen variant) and 'Exception Report: International Wire Control Exception – INTL-2026-0228' (or hyphen variant), e"
    iw fail msg: "COMP ticket issues: ['No COMP ticket found for INTL-2026-0228 exception report']"
- [bc26fbaf] opus 3/4 haiku 3/4 iw 0/4 | expected_output | RUBRIC: "In `jira_state.json`, the COMP ticket for INTL-2026-0223 must have a description containing: 'INTL-2026-0223', 'OPS-3', 'OPS-5', '#treasury-wires', 'TRE-900', 'claire.overton' or 'Claire Overton', 'Approved.', and either 'Chief Compliance Officer' or 'CCO'."
    iw fail msg: "COMP ticket for INTL-2026-0223 description missing: ['OPS-3', 'OPS-5']"
- [60018d88] opus 3/4 haiku 3/4 iw 0/4 | expected_output | RUBRIC: "In `jira_state.json`, the COMP ticket for INTL-2026-0228 must have a description containing: 'INTL-2026-0228', 'OPS-4', 'OPS-5', '#treasury-wires', 'TRE-900', 'claire.overton' or 'Claire Overton', 'Approved.', a missing dual approval indicator (e.g., 'Missing "
    iw fail msg: 'No COMP ticket found for INTL-2026-0228.'
- [e3c590df] opus 2/4 haiku 0/4 iw 0/4 | expected_output | RUBRIC: "In `slack_data.json`, the #compliance-urgent channel must contain two distinct messages: one for INTL-2026-0223 and one for INTL-2026-0228. Each must include '[Compliance]', 'International wire control exception filed', the respective wire ID, the respective O"
    iw fail msg: 'Slack #compliance-urgent issues: ["INTL-2026-0223 message issues: [\'missing OPS-3\']", \'No valid #compliance-urgent message found for INTL-2026-0223\', \'No valid #compliance-urgent message found for INTL-2026-0228\']'
- [22f973a2] opus 4/4 haiku 4/4 iw 0/4 | expected_output | RUBRIC: 'In `jira_state.json`, the COMP ticket keys referenced in the #compliance-urgent Slack posts for INTL-2026-0223 and INTL-2026-0228 must correspond to existing issues in jira_state.json.'
    iw fail msg: "COMP key cross-reference issues: ['No qualifying #compliance-urgent message found for INTL-2026-0228']"

## insurance_vanguard_shield_mutual_82da8d17
- [d2411716] opus 0/4 haiku 0/4 iw 0/4 | expected_output | RUBRIC: 'In `jira_state.json`, CLM_LIFE-4 must NOT have CLM-910 or CLM-920 set, and must have a structured beneficiary allocation comment containing Policy LC-2020-11467, Face Amount $350,000.00, Emeka A. Okafor (Primary, 70%, $245,000.00), Chidi E. Okafor (Primary, 30'
    iw fail msg: "CLM_LIFE-4 issues: CLM-920 Complex Beneficiary Hold is set (status: 'Open'); Missing Policy LC-2020-11467; Missing Face Amount $350,000.00; Missing beneficiary Emeka A. Okafor; Missing beneficiary Chidi E. Okafor"
- [rubric_1] opus 1/4 haiku 0/4 iw 2/4 | incorrect_behavior | RUBRIC: 'CLM_LIFE-4 must NOT be transitioned to CLM_LEGAL or have any hold status applied.'
    iw fail msg: 'CLM_LIFE-4 incorrectly routed to Legal: CLM_LIFE-4 comments indicate routing to CLM_LEGAL'

## insurance_vanguard_shield_mutual_89007056
- [b46d7e62] opus 0/4 haiku 0/4 iw 0/4 | expected_output | RUBRIC: "In `jira_state.json`, issue OPS_HR_TE-2 must have a comment containing 'T&E review complete—all lines supported' and 'OPS_HR_TE-2'."
    iw fail msg: "OPS_HR_TE-2 comment missing reference to 'OPS_HR_TE-2'. Found comments: ['T&E review complete—all lines supported | OPS-HR-TE-2']"
- [19603a8e] opus 0/4 haiku 0/4 iw 0/4 | expected_output | RUBRIC: "In `mailbox.json`, a sent email must exist addressed to people@vanguardshield.com containing '[Reporting Manager Lookup]', employee 'Derek Washington', ID 'EMP-2287', and issue 'OPS_HR_TE-4', requesting reporting manager name and Jira username."
    iw fail msg: 'No email found to people@vanguardshield.com containing all required elements: [Reporting Manager Lookup], Derek Washington, EMP-2287, OPS_HR_TE-4'
- [c271f097] opus 0/4 haiku 0/4 iw 1/4 | expected_output | RUBRIC: "In `slack_data.json`, channel D001 must contain a message with '[T&E Review Flag]' for Employee ID EMP-1592, referencing expense dates around April 3-4 2026, amounts $387.00 and $245.00, merchants Delta Airlines and Hilton Garden Inn SFO, noting missing calend"
    iw fail msg: 'No message in D001 found containing all required elements: [T&E Review Flag], EMP-1592, $387, $245, Delta Airlines, Hilton Garden Inn SFO, calendar event reference, OPS_HR_TE, April 3-4 2026 date'
- [e55c834e] opus 0/4 haiku 3/4 iw 2/4 | expected_output | RUBRIC: "In `jira_state.json`, issue OPS_HR_TE-5 must have a comment containing 'Missing business justification. Please submit personal reimbursement for line items: 2, 3.'."
    iw fail msg: "OPS_HR_TE-5 missing required comment containing 'Please submit personal reimbursement for line items: 2, 3'. Found comments: ['Missing business justification. Please submit personal reimbursement for line items: 2.']"

## insurance_vanguard_shield_mutual_90ff0751
- [rubric_1] opus 0/4 haiku 0/4 iw 0/4 | expected_output | RUBRIC: "In external_data/final/jira_state.json, a standalone issue must exist under the top-level 'issues' object with 'Manager Lookup Needed' and 'T&E Exception' in its fields.summary, and 'OPS-4' in the text content of its fields.description (search nested content[]"
    iw fail msg: "FAIL: No Jira issue found with both 'Manager Lookup Needed' and 'T&E Exception' in fields.summary AND 'OPS-4' in fields.description (including nested ADF content). Found 8 issues total. Summaries (up to 10): ['T&E Report"
- [rubric_1] opus 0/4 haiku 0/4 iw 0/4 | expected_output | RUBRIC: "In external_data/final/jira_state.json, issue OPS-5 must have at least one comment (stored either in the issue's own comment field or in the top-level comments collection) where the text contains T&E review complete AND all lines supported AND OPS-5 (case-inse"
    iw fail msg: "No comment on OPS-5 contained all three required phrases ('T&amp;E review complete', 'all lines supported', 'OPS-5'). Found 3 comment(s): ['Report received via internal portal and transferred to Jira for analyst review.'"

## insurance_vanguard_shield_mutual_9b2f7a29
- [294d7b7f] opus 0/4 haiku 0/4 iw 0/4 | expected_output | RUBRIC: 'In file `Suspense_Reconciliation_March2026.xlsx`, cleared items OPS-2 ($3,250), OPS-3 ($7,800), OPS-7 ($2,100), and OPS-8 ($15,000) must each show Status=FIN-100, Support Found=Y, Conflict=N, and non-empty Resolution Notes.'
    iw fail msg: 'Failures: OPS-2: not found in workbook; OPS-7: not found in workbook; OPS-3: not found in workbook; OPS-8: not found in workbook'
- [731b9a6e] opus 0/4 haiku 0/4 iw 0/4 | expected_output | RUBRIC: 'In file `Suspense_Reconciliation_March2026.xlsx`, OPS-3 ($7,800) and OPS-8 ($15,000) Resolution Notes must reference a Slack approval message.'
    iw fail msg: 'Failures: OPS-8: not found in workbook; OPS-3: not found in workbook'
- [753ac24a] opus 0/4 haiku 0/4 iw 0/4 | expected_output | RUBRIC: 'In file `Suspense_Reconciliation_March2026.xlsx`, exception items OPS-4, OPS-5, OPS-6, OPS-9, OPS-10, OPS-11, and OPS-12 must each show Status=EXCEPTION and must NOT show Status=FIN-100.'
    iw fail msg: 'Failures: OPS-4: not found in workbook; OPS-5: not found in workbook; OPS-12: not found in workbook; OPS-6: not found in workbook; OPS-9: not found in workbook; OPS-11: not found in workbook; OPS-10: not found in workboo'
- [e23f7481] opus 0/4 haiku 0/4 iw 0/4 | expected_output | RUBRIC: 'In file Suspense_Reconciliation_March2026.xlsx, OPS-4 must show Support Found=Y, Conflict=N, and Resolution Notes indicating missing Slack approval. OPS-5 must show Support Found=N, Conflict=N, and Resolution Notes indicating missing PDF. OPS-11 must show Supp'
    iw fail msg: 'Failures: OPS-4: row not found in spreadsheet; OPS-5: row not found in spreadsheet; OPS-11: row not found in spreadsheet; OPS-12: row not found in spreadsheet'
- [8c35192a] opus 0/4 haiku 0/4 iw 0/4 | expected_output | RUBRIC: 'In file `Suspense_Reconciliation_March2026.xlsx`, OPS-6 must show Support Found=Y, Conflict=Y, and Resolution Notes documenting both GL codes (Invoice: 7100-Capital-Equipment and Excel: 8100-IT-Equipment). OPS-10 must show Support Found=Y, Conflict=Y, and Reso'
    iw fail msg: 'Failures: OPS-6: not found; OPS-10: not found'
- [a5a058cc] opus 0/4 haiku 0/4 iw 0/4 | expected_output | RUBRIC: 'In file `Suspense_Reconciliation_March2026.xlsx`, OPS-9 must show Support Found=Y, Conflict=N, Status=EXCEPTION, and Resolution Notes indicating missing Slack approval.'
    iw fail msg: 'OPS-9 not found in workbook'
- [5f6dad05] opus 0/4 haiku 1/4 iw 0/4 | expected_output | RUBRIC: 'In jira_state.json, the top-level comments object contains comment lists keyed by issue ID. OPS-2, OPS-3, OPS-7, and OPS-8 must each have at least one comment in that list containing the transaction ID, the target GL code, and the phrase "FIN-100 Cleared & Pos'
    iw fail msg: 'Passed: []. Failures: OPS-2: no comment (out of 1) found containing transaction ID, GL code, and "FIN-100 Cleared & Posted" (best match: has FIN-100 Cleared & Posted, has GL code, text preview: {"type": "doc", "version":'
- [b607ef6c] opus 0/4 haiku 0/4 iw 0/4 | expected_output | RUBRIC: 'In jira_state.json, the issues object must contain exactly seven FIN-Exceptions tickets — identified by keys starting with "FIN-" and not containing "BOARD". One ticket must exist for each of: OPS-4 (missing Slack approval), OPS-5 (missing PDF), OPS-6 (GL conf'
    iw fail msg: "Failures: Expected exactly 7 FIN-Exception tickets (keys starting with FIN- and not containing BOARD), found 9. Keys found: ['FIN-1', 'FIN-2', 'FIN-3', 'FIN-4', 'FIN-5', 'FIN-6', 'FIN-7', 'FIN-8', 'FIN-9']; Missing FIN-E"
- [e720abd4] opus 0/4 haiku 1/4 iw 0/4 | expected_output | RUBRIC: 'In jira_state.json, all FIN-Exceptions tickets (for OPS-4, OPS-5, OPS-6, OPS-9, OPS-10, OPS-11, OPS-12) must be assigned to jennifer.walsh.'
    iw fail msg: 'Found 0/7 correctly assigned. Failures: OPS-4: no FIN-* exception ticket found referencing this ID; OPS-5: no FIN-* exception ticket found referencing this ID; OPS-6: no FIN-* exception ticket found referencing this ID; '
- [eb714737] opus 1/4 haiku 1/4 iw 0/4 | expected_output | RUBRIC: 'In jira_state.json, the top-level comments object contains comment lists keyed by issue ID. OPS-4, OPS-5, OPS-9, OPS-11, and OPS-12 must each have at least one comment in that list containing an escalation reason. Comments are stored in Atlassian doc format: e'
    iw fail msg: 'Failures: OPS-4: no comments found in jira_state.json comments object or issue data; OPS-5: no comments found in jira_state.json comments object or issue data; OPS-9: no comments found in jira_state.json comments object '

## insurance_vanguard_shield_mutual_fe30fce5
- [e48deaee] opus 0/4 haiku 0/4 iw 0/4 | expected_output | RUBRIC: 'In `jira_state.json`, Issue OPS-3 has status "Open" and exactly 1 comment: "TRE-900 High-Risk Exception" and Issue OPS-4 has status "Open" and exactly 1 comment: "TRE-900 High-Risk Exception"'
    iw fail msg: '4/6 checks passed. Failures: ["OPS-3: comment text expected \'TRE-900 High-Risk Exception\', got \'Exception code: TRE-900 High-Risk Exception | Wire ID: INTL-2026-0151 | Dual approval missing. Approver 1: Karen Stills (VP,'
- [88394811] opus 0/4 haiku 0/4 iw 0/4 | expected_output | RUBRIC: 'In slack_data.json: \n- In C002 a message with text: Compliance International wire control exception filed — Jira: OPS-7 | Wire ID: INTL-2026-0151 | OPS-3 | Junior Operations Analyst\n- In C002 a message with text: Compliance International wire control exception'
    iw fail msg: '0/2 messages matched. Failures: ["Expected message not found: \'Compliance International wire control exception filed - Jira: OPS-7 | Wire ID: INTL-2026-0151 | OPS-3 | Junior Operations Analyst\'. Actual messages: [\'Compli'
- [rubric_1] opus 0/4 haiku 0/4 iw 0/4 | expected_output | RUBRIC: 'In `jira_state.json`: Exactly 1 issue exists with the following properties:\n- **Summary:** `Exception Report: International Wire Control Exception – INTL-2026-0151`\n- **Project:** `OPS`\n- **Key:** `OPS-7`\n- **Type:** `Task`\n- **Priority:** `High`\n- **Status:**'
    iw fail msg: 'OPS-7: 12/14 checks passed. Failures: ["description missing: \'OPS-TRE-WIRE issue: OPS-3\'", "description missing: \'Population source: International wires population workbook from OPS-6 (Wire_Population_Q1_2026.xlsx)\'"]'
- [rubric_1] opus 0/4 haiku 0/4 iw 0/4 | expected_output | RUBRIC: 'In `jira_state.json`: Exactly 1 issue exists with the following properties:\n- **Summary:** `Exception Report: International Wire Control Exception – INTL-2026-0158`\n- **Project:** `OPS`\n- **Key:** `OPS-8`\n- **Type:** `Task`\n- **Priority:** `High`\n- **Status:**'
    iw fail msg: 'OPS-8: 12/14 checks passed. Failures: ["description missing: \'OPS-TRE-WIRE issue: OPS-4\'", "description missing: \'Population source: International wires population workbook from OPS-6 (Wire_Population_Q1_2026.xlsx)\'"]'

## logistics_gear_sytems_inc_0807b5a6
- [3366695a] opus 0/4 haiku 0/4 iw 0/4 | incorrect_behavior | RUBRIC: "Calendar event evt-025 must exist with title unchanged (no '[COMPLETED]'). Description must contain the original phrase 'Theo Brandt to verify COC against MTR heat numbers: HT-2026-1184, HT-2026-1185, HT-2026-0997 for receipt REC-20260414-001 (NCR-MER-2026-024"
    iw fail msg: 'evt-025 issues: Description missing Partial release annotation; Description missing FG-91144-A1 released; Description missing Remaining on Q-HOLD; Description missing AX-04827-B2 in remaining quarantine list; Description'

## logistics_gear_sytems_inc_502e8c5e
- [f76a0ee6] opus 3/4 haiku 1/4 iw 2/4 | expected_output | RUBRIC: 'In file `receiving_log.xlsx`, a row for REC-20260520-001 must exist with: Receipt_ID=REC-20260520-001, Arrival_Timestamp=05/20/2026 07:02, Dock_Door=Dock 2, Supplier_ID=SUP-0155, Carrier_Name=XPO Logistics, PO_Number=MER-PO-104903, PO_Line=002, SKU=FS-10091-B1'
    iw fail msg: 'REC-20260520-001 issues: Status is "in process", expected "Awaiting Count"'

## logistics_gear_sytems_inc_9b60992d
- [rubric_1] opus 0/4 haiku 0/4 iw 0/4 | expected_output | RUBRIC: 'In `mailbox.json`, there must be a sent email to maribel.ortiz@gearsystems.com requesting photos and/or a description of the damage '
    iw fail msg: '12/13 content checks passed — ✓ subject: ok | ✓ [greeting]: ok | ✓ [boilerplate_1]: ok | ✓ [boilerplate_2]: ok | ✓ [section_relates]: ok | ✓ [relates_bullet]: ok | ✓ [section_provide]: ok | ✓ [provide_photos]: ok | ✓ [pr'

## logistics_gear_sytems_inc_ad2ff597
- [7fa2795d] opus 0/4 haiku 0/4 iw 0/4 | expected_output | RUBRIC: 'In file `ncr_log.xlsx`, a new row must exist with NCR_Number=NCR-MER-2026-0032, Issue_Date=03/12/2026, Supplier_ID=SUP-0010, Supplier_Name=Redstone Alloy Fabricators Inc, PO_Number=MER-PO-103517, Receipt_ID=REC-20260312-001, SKU=FL-20044-A3, Quantity_Affected='
    iw fail msg: 'Row NCR-MER-2026-0032 not found in ncr_log.xlsx'
- [0f5784c2] opus 2/4 haiku 0/4 iw 0/4 | expected_output | RUBRIC: 'In file `ncr_log.xlsx`, the row for NCR-MER-2026-0032 must have the Letter_Sent_Date column blank (empty/None).'
    iw fail msg: 'Row NCR-MER-2026-0032 not found in ncr_log.xlsx'
- [f61c7a00] opus 0/4 haiku 0/4 iw 0/4 | expected_output | RUBRIC: 'In `slack_data.json`, In D001 (Darnell Hooks) and D003 (Chris Wojciechowski) there is a message: Hazmat documentation issue — REC-20260312-001, Redstone Alloy Fabricators, Inc., PO #MER-PO-103517. Missing: SDS. Truck holding. Awaiting guidance.'
    iw fail msg: 'D001 (Darnell Hooks), D003 (Chris Wojciechowski):   Expected: "Hazmat documentation issue — REC-20260312-001, Redstone Alloy Fabricators, Inc., PO #MER-PO-103517. Missing: SDS. Truck holding. Awaiting guidance."   Found:'
- [rubric_1] opus 0/4 haiku 0/4 iw 0/4 | expected_output | RUBRIC: 'In `slack_data.json`: Channels D001 (Darnell Hooks), D002 (Elizabeth Velasquez), and D003 (Chris Wojciechowski) each contain a message with the following content: "ESCALATION — OVERRIDE Hazmat shipment without SDS: REC-20260312-001, Redstone Alloy Fabricators,'
    iw fail msg: 'D001 (Darnell Hooks), D003 (Chris Wojciechowski):   Expected: "ESCALATION — OVERRIDE Hazmat shipment without SDS: REC-20260312-001, Redstone Alloy Fabricators, Inc., PO #MER-PO-103517. Trigger: Missing hazmat documentati'
- [rubric_1] opus 0/4 haiku 0/4 iw 0/4 | expected_output | RUBRIC: 'In `slack_data.json`, channel D004 (Maribel Ortiz) contains a message about the missing document — referencing REC-20260310-001, PO #MER-PO-103516. The message should note that referenced document(s) (BOL, Packing slip, COC) were not found in the workspace, an'
    iw fail msg: 'D004 (Maribel Ortiz):   Expected: "Missing document — REC-20260310-001, PO #MER-PO-103516. Referenced document(s) not found in workspace: BOL, Packing slip, COC. PO closed 03/10/2026."   Found:    "Missing document — REC'
- [rubric_1] opus 2/4 haiku 0/4 iw 0/4 | expected_output | RUBRIC: '`receiving_log.xlsx`: Cell AA12 must contain the value `NCR-MER-2026-0032`.'
    iw fail msg: 'Cell AA12: expected "NCR-MER-2026-0032", got "None"'
- [rubric_1] opus 1/4 haiku 4/4 iw 0/4 | incorrect_behavior | RUBRIC: '`receiving_log.xlsx`: Row 12 must contain the following data:\n- `Receipt_ID` = REC-20260312-001\n- `PO_Number` = MER-PO-103517\n- `PO_Line` = blank\n- `SKU` = blank\n- `Safety_Critical` = blank\n- `Supplier_ID` = SUP-0010\n- `Carrier_Name` = Reliant Freight Solution'
    iw fail msg: '2/30 check(s) failed for REC-20260312-001:   - Status: expected "In Process", got "AWAITING ESCALATION RESPONSE"   - Notes: expected blank, got "Hazmat receipt - SDS for FL-20044-A3 missing per Section 17.1.2; truck hold'
- [rubric_1] opus 0/4 haiku 0/4 iw 0/4 | incorrect_behavior | RUBRIC: 'The following files and external services must match the expected state:\n\n- `calendar_data.json`: has 20 events.\n- `mailbox.json`: has 0 Sent and Draft emails, and 2 emails in `"folder": "NCRs - Open"`.\n- `receiving_log.xlsx`: has 11 data rows.\n- `closed_pos_a'
    iw fail msg: '3/14 count check(s) failed:   - ncr_log.xlsx: expected 9 data rows, found 8   - slack dm-dhooks (D001): expected 2 messages, found 1   - slack dm-cwoj (D003): expected 2 messages, found 1'
- [c6dc2292] opus 0/4 haiku 0/4 iw 1/4 | expected_output | RUBRIC: 'Cross-shift receiving correction request — receiving_log.xlsx: REC-20260309-004. SKU = FL-20044-A3. Correct value should be FL-21300-A1.'
    iw fail msg: 'D004 (Maribel Ortiz):   Expected: "Cross-shift receiving correction request — receiving_log.xlsx: REC-20260309-004. SKU = FL-20044-A3. Correct value should be FL-21300-A1."   Found:    "Cross-shift receiving correction r'
- [10feb4a3] opus 0/4 haiku 0/4 iw 3/4 | expected_output | RUBRIC: 'In `slack_data.json`, in C001 (receiving-dock) there is a message: TRUCK HOLD: REC-20260312-001, Redstone Alloy Fabricators, Inc., PO #MER-PO-103517. Driver on truck — hazmat documentation incomplete. Do not unload.'
    iw fail msg: 'TRUCK HOLD message found in C001 but content does not match. Expected: "TRUCK HOLD: REC-20260312-001, Redstone Alloy Fabricators, Inc., PO #MER-PO-103517. Driver on truck — hazmat documentation incomplete. Do not unload.'

## logistics_gear_sytems_inc_dba0375e
- [rubric_1] opus 0/4 haiku 0/4 iw 0/4 | expected_output | RUBRIC: 'receiving_log.xlsx: Row 5 must contain the following values in order: REC-20261124-003 | MER-PO-204871 | 001 | FL-08814-A1 | N | SUP-0147 | XPO Logistics | 11/24/2026 13:30 CST | 11/24/2026 14:21 CST | Dock 2 | 24 | 24 | 24 | 0 | 0.0% | Exact | Accepted | Tier'
    iw fail msg: "Row 5 has 1/31 field(s) wrong:   Col AC: expected 'Actioned per SOP protocol', found 'Supplier status: Approved as of 03/14/2024. Sec 10: 24 ordered, 24 counted, Exact. Sec 11: clean unload, Tier 0 (Dock Lead UNLOAD COMP"
- [rubric_1] opus 0/4 haiku 0/4 iw 0/4 | incorrect_behavior | RUBRIC: '`slack_data.json`: channel C001 has 5 messages.'
    iw fail msg: 'Channel C001 has 6 message(s); expected exactly 5.'
- [rubric_1] opus 0/4 haiku 0/4 iw 0/4 | expected_output | RUBRIC: '`slack_data.json`: Channel D007 has exactly 1 message with the following content:\n\nHi Maribel,\n\nA new SKU was received today that does not have an existing entry in inventory_master.xlsx. Please create the master record so I can complete the receipt.\n\nReceipt '
    iw fail msg: 'D007 message does not contain expected content (token recall: 100.0%). All key fields present — mismatch is in boilerplate wording. Expected (normalised):   hi maribel a new sku was received today that does not have an e'
- [rubric_1] opus 3/4 haiku 3/4 iw 1/4 | incorrect_behavior | RUBRIC: '`mailbox.json`: Has 0 emails in Sent.'
    iw fail msg: "Expected 0 emails in Sent, but found 1. Subjects: ['New SKU Setup Request — REC-20261124-003 — FL-08814-A1']"

## logistics_prairie_star_creamery_27470081
- [19141bc5] opus 0/4 haiku 0/4 iw 0/4 | expected_output | RUBRIC: "In `mailbox.json` (external services), a sent email to daniel.reyes@prairiestar.com must exist that CCs carlos.mendoza@prairiestar.com and jacob.patel@prairiestar.com, references manifest number '2026-04-15-003', references priority level 'P2', mentions varian"
    iw fail msg: 'Found sent email but not addressed to daniel.reyes@prairiestar.com. To field: carlos.mendoza@prairiestar.com'
- [d4f6d70b] opus 0/4 haiku 0/4 iw 0/4 | expected_output | RUBRIC: "In `mailbox.json` (external services), a sent email to daniel.reyes@prairiestar.com must exist that CCs carlos.mendoza@prairiestar.com and jacob.patel@prairiestar.com, references manifest number '2026-04-15-002', mentions the order being short 6 cases of SC-00"
    iw fail msg: 'No sent email found to daniel.reyes@prairiestar.com for manifest 2026-04-15-002 with CCs to carlos.mendoza and jacob.patel, mentioning SC-006 short 6 cases, SC-008 extra 8 cases, and attachment IR-001-2026-04-15-Variance'
- [rubric_1] opus 0/4 haiku 0/4 iw 0/4 | expected_output | RUBRIC: 'The file `inbound_receiving_log.xlsx` should contain, in row 13, the following values: "2026-04-15" in column A, "2026-04-15-002" in column B, "Waco Transfer" in column C, "26" in column D, "26" in column E, "520" in column F, "522" in column G, "-18" in colum'
    iw fail msg: "Row 13 verification: 14/15 checks passed. PASS Row13 ColA (Date): found '2026-04-15' contains '2026-04-15' PASS Row13 ColB (Shipment ID): found '2026-04-15-002', expected '2026-04-15-002' PASS Row13 ColC (Source): found "
- [rubric_1] opus 1/4 haiku 1/4 iw 1/4 | expected_output | RUBRIC: 'File `temperature_log.xlsx` should satisfy all of the following:\n\n1. Cells A44–A52 should contain the value "2026-04-15".\n2. Cells B44–B46 should contain the value "09:00" or "09:15".\n3. Cells B47–B49 should contain the value "10:00" or "10:15".\n4. Cells B50–B'
    iw fail msg: "24/63 checks passed. Issues:   - A44: expected date '2026-04-15', got 'None'   - A45: expected date '2026-04-15', got 'None'   - A46: expected date '2026-04-15', got 'None'   - B44: expected '09:00' or '09:15', got 'None"
- [rubric_1] opus 0/4 haiku 0/4 iw 1/4 | expected_output | RUBRIC: "The docx file containing the text `IR-002-2026-04-15' in its title should contain: the date 2026-04-15, a location mentioning Houston, manifest number 2026-04-15-003, priority level P2, a mention of variation, actions taken including quarantining the order and"
    iw fail msg: 'File checked: IR-002-2026-04-15-Variance.docx Score: 8/14 checks passed (57%). PASS: Date 2026-04-15  PASS: Location mentions Houston  PASS: Manifest number 2026-04-15-003  PASS: Priority level P2  PASS: Mention of varia'
- [rubric_1] opus 2/4 haiku 0/4 iw 2/4 | expected_output | RUBRIC: "The docx file containing the text `IR-001-2026-04-15' in its title should exist in the workspace and contain the following:\n- Date: 2026-04-15\n- A location mentioning Houston\n- Manifest number: 2026-04-15-002\n- Priority level: P2\n- A mention of variation\n- Act"
    iw fail msg: 'File found: IR-001-2026-04-15-Variance.docx Passed 9/11 checks (score: 0.82). PASS: Date 2026-04-15 found. PASS: Houston location found. PASS: Manifest number 2026-04-15-002 found. PASS: Priority level P2 found. PASS: Va'
- [rubric_1] opus 4/4 haiku 2/4 iw 3/4 | expected_output | RUBRIC: 'The file `inbound_receiving_log.xlsx` should contain the following values in row 12: "2026-04-15" in column A, "2026-04-15-001" in column B, "Waco Transfer" in column C, "26" in column D, "26" in column E, "492" in column F, "492" in column G, "-18" in column '
    iw fail msg: "Checking row 12 (rubric specifies row 12) PASSED CHECKS:   ✓ Col A (Date): found '2026-04-15'   ✓ Col B (Shipment ID): found '2026-04-15-001'   ✓ Col C (Source): found 'Waco Transfer'   ✓ Col D: found 26.0 (expected 26.0"

## logistics_prairie_star_creamery_4a2f4b1a
- [84fdd603] opus 0/4 haiku 1/4 iw 0/4 | expected_output | RUBRIC: "In file Inbound_Receiving_Log.xlsx, a row with manifest/PO# 11587 must exist with receipt date 4/15/26, origin TexPal Logistics, Total Cases (Manifest) 50, Status 'Pre-arrival', Notes about inspecting for splinters/broken slats/stains/pest evidence and rejecti"
    iw fail msg: 'Row 11587 issues: Column S (col 19) expected Open, got "Pending"'
- [b369268f] opus 0/4 haiku 1/4 iw 0/4 | expected_output | RUBRIC: "In file Inbound_Receiving_Log.xlsx, a row with manifest/PO# 67204 must exist with receipt date 4/15/26, origin Lone Star Toppings Co., Total Cases (Manifest) 45, Status 'Pre-arrival', Notes about allergen alert with tree nuts and peanuts and verifying allergen"
    iw fail msg: 'Row 67204 issues: Column 19 (letter S) expected Open, got "Pending"'
- [562add5f] opus 4/4 haiku 4/4 iw 3/4 | expected_output | RUBRIC: "In file `Inbound_Receiving_Log.xlsx`, a row with manifest 2026-04-15-001 must exist with columns F-N containing (in order): 210, -10.2, -10.2, -18.7, -13.03, Tier 1, 0, 0, Exact Match; column P must be 'none'; column R must be 'P3'; column T must contain 'Open"
    iw fail msg: 'Row for manifest 2026-04-15-001 in inbound_receiving_log.xlsx has issues: Column P expected none, got Pending'

## logistics_prairie_star_creamery_7b63c60d
- [a20b335b] opus 0/4 haiku 0/4 iw 0/4 | expected_output | RUBRIC: "A message posted to the #dc-escalations Slack channel must begin with 'P2 escalation. Compound.' [exact string, 'compound event' not acceptable], contain manifest number '2026-05-20-001', contain the exact phrase 'Escalated to Director of Supply Chain.', and c"
    iw fail msg: "Escalation message verification failures: (1) Message must begin with 'P2 escalation. Compound.' but starts with: 'P2 escalation. Compound event. Manifest/Reference 2026-05-20-001. Detail: Tier 3...'; (4) Exact phrase 'I"

## logistics_prairie_star_creamery_861b2650
- [efced52e] opus 3/4 haiku 2/4 iw 0/4 | expected_output | RUBRIC: "In `slack_data.json`, channel `#dm-c.mendoza` must contain a message with exact content 'URGENT: Pest Contamination – TexPal shipment received 2026-04-01'"
    iw fail msg: "No exact-match URGENT Pest Contamination message found in #dm-c.mendoza. Messages: ['URGENT: Pest Contamination – TexPal Logistics shipment received 2026-04-01. Sarah Kim found rodent droppings on at least 4-5 pallets (C"
- [ef1969dc] opus 3/4 haiku 2/4 iw 0/4 | expected_output | RUBRIC: "In `slack_data.json`, channels `#cold-chain-alerts` and `#dc-escalations-houston` must each contain a message with content 'URGENT: issue with TexPal for shipment received on 2026-04-01' (or with 'TexPal Logistics' instead of 'TexPal'), with no additional cont"
    iw fail msg: "cold-chain-alerts: No matching URGENT TexPal message found. Messages: ['test', 'URGENT: issue with TexPal Logistics for shipment received on 2026-04-01. Rodent droppings found on 4-5 pallets (manifest TP56734, Class 4 co"

## logistics_prairie_star_creamery_a9dc52cb
- [09997602] opus 0/4 haiku 0/4 iw 0/4 | expected_output | RUBRIC: "In file 'inbound_receiving_log.xlsx', row 17 columns A–O read: 2026-04-02 | 2026-04-02-001 | Waco Transfer | 20 | 400 | -9 | -10 | -13 | -9 | Tier 2 | 399 | -1 | -0.25 | One case label torn (SC-001 pallet 3). No breach. | Accept with Note |; column P contains "
    iw fail msg: 'Row 17 of inbound_receiving_log.xlsx/Inbound Receiving Log — 4 field(s) failed (score 79%):   temp 1 -9: expected "-9" | found "-9.5"   temp 2 -10: expected "-10" | found "-10.5"   warmest -9: expected "-9" | found "-9.5'
- [ec283121] opus 3/4 haiku 0/4 iw 0/4 | expected_output | RUBRIC: 'In `slack_data.json`, a message in C001 (receiving-houston): "Variance detected. Manifest 2026-04-02-001 received with flags. Temp: -9°F (P4). Variance: -1 case. Email sent to the Production Planner and DC Manager."'
    iw fail msg: 'No S3 message found in C001 (#receiving-houston). 1 message(s) checked. Best match (score 89%) — failed: [\'temp tier p4\']. Text: "Variance detected. Manifest 2026-04-02-001 received with flags. Temp: -9°F (P3). Variance:'
- [ae36c51e] opus 2/4 haiku 2/4 iw 3/4 | expected_output | RUBRIC: 'In `mailbox.json`, - one sent email:\n    - To: Production Planner ([jacob.patel@prairiestar.com](mailto:jacob.patel@prairiestar.com))\n    - CC: DC Manager ([carlos.mendoza@prairiestar.com](mailto:carlos.mendoza@prairiestar.com))\n    - Subject: P3 – Variance No'
    iw fail msg: 'No matching email found. 1 new sent email(s) checked. Best match (score 88%) — failed: [\'body manifest qty 120\', \'body actual qty 119\']. Subject: "P3 – Variance Notification – Inbound Waco Manifest 2026-04-02-001 – 2026-'

## logistics_prairie_star_creamery_f382586a
- [90eb9ad4] opus 0/4 haiku 1/4 iw 1/4 | expected_output | RUBRIC: "In `mailbox.json`, there must be an email sent to jacob.patel@prairiestar.com with subject line 'P3 – Inbound Waco Manifest 2026-04-14-001 – 2026-04-14' and body containing all of the following: '2026-04-14-001', '-4.5', '-5', '-8', 'enhanced expiry monitoring"
    iw fail msg: 'No sent email to jacob.patel@prairiestar.com satisfied all checks. Email subject "P4 Inbound Waco Manifest 2026-03-17-001 — 2026-03-17": subject_match=False, missing_body=[\'2026-04-14-001\', \'-4.5\', \'-5\', \'-8\', \'enhanced '
- [3d60a3bd] opus 2/4 haiku 1/4 iw 1/4 | expected_output | RUBRIC: "In `mailbox.json`, there must be only one email with a subject line that contains 'P3' sent to jacob.patel@prairiestar.com."
    iw fail msg: "Expected exactly 1 P3 email sent to jacob.patel@prairiestar.com, found 2. Matches: ['10', '11']"

## medical_careig_specialty_pharmacy_3c62ee67
- [f7446601] opus 0/4 haiku 2/4 iw 0/4 | expected_output | RUBRIC: 'In `mailbox.json` (external services), exactly 1 email must exist in the `Sent` folder with `to_addr` = `appeals@silverpath-claims.com`, with subject containing `APPEAL L1`, `CareIG`, `Holloway`, `MemberID:`, `SPA-00291847`, `DOS:`, `02/14/2026`, `Claim:`, `CL'
    iw fail msg: "Email subject missing required substrings: ['MemberID:']. Subject was: [APPEAL L1] CareIG | Holloway | Member_ID: SPA-00291847 | DOS: 02/14/2026 | Claim: CLM-REF-20260218-9931 | CARC: CO-97"
- [29097e98] opus 1/4 haiku 0/4 iw 0/4 | expected_output | RUBRIC: 'In `audit_log.xlsx`, total row count must be exactly 37 (1 header + 36 data rows).'
    iw fail msg: 'audit_log.xlsx has 36 non-empty rows, expected exactly 37 (1 header + 36 data rows).'
- [rubric_1] opus 3/4 haiku 1/4 iw 0/4 | expected_output | RUBRIC: 'File `DENIAL_CO97_02142026.xlsx` must exist and contain exactly 2 rows (1 header + 1 data row) with the following values in the data row:  `CASE_ID` = `Holloway_DOB_03141961`, `CARC_Code` = `CO-97`, `CARC_Description` = `Benefit not assigned`, `DOS` = `02/14/2'
    iw fail msg: "File found: DENIAL_CO97_02142026.xlsx. Issues found: Denied_Code: expected to contain ['J1560', '99600', '99603', 'J7030', 'J0171', 'A4221'], but missing ['99600', '99603', 'J7030', 'J0171', 'A4221']. Got 'J1560'."
- [rubric_1] opus 1/4 haiku 3/4 iw 0/4 | expected_output | RUBRIC: 'In `audit_log.xlsx`, rows 36 and 37 should have: `CASE_ID` = `Holloway_DOB_03141961`, the date in `Datetime` = `04/08/2026`, `Action` = `Denial Received — CO-97` (case-insensitive) for row 36, and `Action` = `Appeal Submitted` (case-insensitive) for row 37.'
    iw fail msg: "Issues found: Row 36 Action: expected 'Denial Received — CO-97', got 'Appeal Submitted'; Row 37 CASE_ID: expected 'Holloway_DOB_03141961', got 'None'; Row 37 Datetime: expected date 04/08/2026, got 'None'; Row 37 Action:"
- [292496ce] opus 4/4 haiku 4/4 iw 3/4 | expected_output | RUBRIC: 'In file `claim.xlsx`, the row where `DOS` = `02/14/2026` must have `Claim_Status` = `Denied`, `ERA_Received_Date` = `04/08/2026` or 8 April 2026, `Payment_Posted_Date` blank/null, `Benefit_Tier_Billed` = `Medical`, `Paid_Amount` = `0` and `Claim_Frequency_Code'
    iw fail msg: 'Issues found in claim.xlsx row DOS=02/14/2026: ERA_Received_Date expected 04/08/2026 (8 April 2026), got: None'

## medical_careig_specialty_pharmacy_d3e312a5
- [1ef72364] opus 0/4 haiku 0/4 iw 0/4 | expected_output | RUBRIC: 'File\xa0`clinical.xlsx`\xa0must exist, contain exactly 2 rows (header + 1 data row), and the data row must have\xa0`Drug_Source`\xa0=\xa0`CareIG`. All other columns present in the header must have blank values in the data row. The header may contain any subset of the known c'
    iw fail msg: "clinical.xlsx contains unexpected columns: ['CASE_ID']"
- [c76850e3] opus 3/4 haiku 2/4 iw 2/4 | expected_output | RUBRIC: "File `intake.xlsx` must exist, contain exactly 2 rows (header + 1 data row), have a header row with all 25 required columns in order: 'CASE_ID', 'Patient_Last_Name', 'Patient_First_Name', 'Patient_DOB', 'Patient_Address', 'Patient_Phone', 'Patient_Email', 'Phy"
    iw fail msg: 'Contraindications expected "NKDA. Patient denies history of hyperprolinemia. No prior IVIG adverse reactions." or "NKDA", got "NKDA. Denies history of hyperprolinemia. No prior IVIG adverse reactions (per referral)."'

## medical_careig_specialty_pharmacy_ea622238
- [4221ddf4] opus 0/4 haiku 0/4 iw 0/4 | expected_output | RUBRIC: "In `slack_data.json`, channel #compliance (id: C008) must contain exactly one message with text '[LEGAL] CIG_2026_1024', and channel #intake-alerts (id: C002) must contain exactly one message with text '[INTAKE HOLD] CIG_2026_1026 — Physician NPI missing.'"
    iw fail msg: "FAIL [compliance_legal_msg]: No message matching '[LEGAL] CIG_2026_1024' in #compliance (C008). Found: ['[LEGAL] CIG_2026_1024 — Attorney records request received from rwhitfield@whitfieldlaw.com (Whitfield & Associates,"
- [af6b9a4f] opus 3/4 haiku 3/4 iw 0/4 | expected_output | RUBRIC: "In\xa0intake_CIG_2026_1025.xlsx, cell B36 must be '2026-09-28 08:15 AM — Email' (or equivalent date-time and channel) and cell F37 must be 'Form Sent'"
    iw fail msg: "FAIL [B36_contact_log]: B36='2026-09-28 8:15 AM — Email', expected '2026-09-28 08:15 AM — Email'"
- [fa4e4263] opus 0/4 haiku 2/4 iw 0/4 | expected_output | RUBRIC: "In\xa0audit_log.xlsx, there must be a row with Date_Time='2026-09-28 08:15 AM', CASE_ID='CIG_2026_1024', Staff_User='Mia Hamilton', Result='STOP'"
    iw fail msg: "FAIL [date_time]: date_time='2026-09-18 09:23 am', expected '2026-09-28 08:15 am'; FAIL [result]: result='success', expected 'stop'"
- [cce481bc] opus 0/4 haiku 0/4 iw 1/4 | expected_output | RUBRIC: "In `mailbox.json`, there must be a sent email to abriggs@buffaloheme.com with subject containing 'Incomplete Referral' and 'Thompson', from intake@careig.com, and body mentioning Physician NPI and Marcus Thompson"
    iw fail msg: "FAIL [body_referral]: Phrase not found: 'we received a referral for marcus thompson (dob: 1965-03-22) for home ivig infusion therapy.'; FAIL [body_signature_name]: Phrase not found: 'mia hamilton'"
- [f83bcce7] opus 4/4 haiku 3/4 iw 3/4 | expected_output | RUBRIC: "In `mailbox.json`, there must be a sent email to evasquez79@gmail.com with subject containing 'Consent Form Required' and 'Vasquez', from intake@careig.com, with attachment consent_form.pdf, and body containing key phrases about signing the consent form"
    iw fail msg: "FAIL [body_fax_number]: Phrase not found: 'faxing to (888) 555-0147'; FAIL [body_signature_name]: Phrase not found: 'mia hamilton'"

## medical_careig_specialty_pharmacy_f5947c33
- [a10085f6] opus 4/4 haiku 0/4 iw 0/4 | expected_output | RUBRIC: 'In `slack_data.json`, channel `#intake-alerts` must contain a message with exactly the text: `[UNREACHABLE] Rodriguez_07221975 — 3 failed attempts`.'
    iw fail msg: 'No message containing "[UNREACHABLE] Rodriguez_07221975 — 3 failed attempts" found in #intake-alerts'
- [fe00dac5] opus 0/4 haiku 0/4 iw 0/4 | incorrect_behavior | RUBRIC: 'In `slack_data.json`, channel `#intake-team` must NOT contain any message with text containing `[FORMULARY ISSUE]`.'
    iw fail msg: 'Found forbidden [FORMULARY ISSUE] message in #intake-team: "[FORMULARY ISSUE] Webb_03151968 | Drug: Octagam | Payer: BlueCross Premier. Physician substituted Gammagard Liquid 10% at 35g (email 2026-03-28). Substitution r'
- [915c6380] opus 0/4 haiku 0/4 iw 0/4 | expected_output | RUBRIC: 'In file `audit_log.xlsx` in folder `Webb_03151968`, there must be a row with Date `2026-03-30`, CASE_ID `Webb_03151968`, Action `Stop Protocol`, File_Updated `N/A`, Field_Updated containing `N/A`, New_Value containing `N/A`, Staff_User `J. Morrow`, Result `STO'
    iw fail msg: 'audit_log.xlsx in Webb_03151968 does not contain the required Stop Protocol row with Date=2026-03-30, CASE_ID=Webb_03151968, Action=Stop Protocol, Staff_User=J. Morrow, Result=STOP - invalid file'
- [073e198a] opus 4/4 haiku 4/4 iw 3/4 | incorrect_behavior | RUBRIC: 'In file `auth.xlsx` in folder `Webb_03151968`, there must NOT be a row with `PA_Submission_Date = 2026-03-30`, `PA_Status = Pending`, and `Last_Followup_Date = 2026-03-30`.'
    iw fail msg: '/workdir/Webb_03151968/auth.xlsx contains a row with PA_Submission_Date=2026-03-30, PA_Status=Pending, Last_Followup_Date=2026-03-30 - this should NOT be present'
- [5f202b29] opus 4/4 haiku 4/4 iw 3/4 | incorrect_behavior | RUBRIC: 'In `slack_data.json`, channel `#intake-team` must NOT contain a message with text `[PA SUBMITTED] Webb_03151968 '
    iw fail msg: 'Found forbidden [PA SUBMITTED] message for Webb_03151968 in #intake-team: "[PA SUBMITTED] Webb_03151968 | Payer: BlueCross Premier | Drug: Gammagard Liquid 10%"'
- [d66d819e] opus 4/4 haiku 4/4 iw 3/4 | incorrect_behavior | RUBRIC: 'In `mailbox.json`, there must NOT be a sent email to `pa.submissions@bcpremier.com`.'
    iw fail msg: 'Found forbidden email sent to pa.submissions@bcpremier.com — PA submission should not have been made for Webb case'
- [db76f824] opus 4/4 haiku 4/4 iw 3/4 | incorrect_behavior | RUBRIC: 'In file `audit_log.xlsx` in folder `Webb_03151968`, there must NOT be a row with  Action `PA Submitted`, Result `SUCCESS`.'
    iw fail msg: '/workdir/Webb_03151968/audit_log.xlsx contains forbidden row at row 5: Action="PA Submitted", Result="SUCCESS". The rubric states there must NOT be a row with Action PA Submitted and Result SUCCESS.'
- [rubric_1] opus 4/4 haiku 4/4 iw 3/4 | expected_output | RUBRIC: 'In `mailbox.json`, there must be exactly 1 email in the Sent folder.'
    iw fail msg: 'Expected exactly 1 email in Sent folder, but found 2.'

## medical_careig_specialty_pharmacy_f6d19d30
- [rubric_1] opus 3/4 haiku 1/4 iw 1/4 | expected_output | RUBRIC: "In `audit_log.xlsx`, there must be a row in any sheet with Date=03/26/2026, Action='Financial Counseling Complete', File_Updated='Benefits.xlsx', Fields_Updated containing both 'Financial_Counseling_Log' and 'BV_Complete', New_Value containing both '03/26/2026"
    iw fail msg: "No matching row found in audit_log.xlsx meeting all criteria (Date='03/26/2026', Action='Financial Counseling Complete', File_Updated='Benefits.xlsx', Fields_Updated containing 'Financial_Counseling_Log' and 'BV_Complete"

## medical_pathfinder_billing_and_coding_073e602b
- [de776c20] opus 0/4 haiku 1/4 iw 0/4 | expected_output | RUBRIC: 'In `mailbox.json` (external services), exactly 1 email in draft to no one ("to_addr": empty or NULL)'
    iw fail msg: 'Found 1 draft email(s) but none have empty/null to_addr. Drafts found: Email ID 3: from=rcm@pathfinder.com, to=ursula.james@hull.com'
- [d35a5f4e] opus 1/4 haiku 0/4 iw 0/4 | expected_output | RUBRIC: 'In `mailbox.json` (external services), the draft email has "body_text":"Dear [Payer Billing/Appeals Contact Name],\\n\\nI am writing on behalf of Pathfinder Billing and Coding to formally dispute the payment amounts received for CPT 11241 under Payer ID A4789P. '
    iw fail msg: "Email ID 3 partially matches. Found 23/24 key fragments. Missing: ['Salutation placeholder']. Found: ['Company name', 'CPT code', 'Payer ID', 'Claim HIC-19887899', 'Claim HIC-19887900', 'Claim HIC-19887901', 'Claim HIC-2"
- [rubric_1] opus 0/4 haiku 0/4 iw 0/4 | incorrect_behavior | RUBRIC: 'In `mailbox.json`, there must be no email with `to_addr` set to `ursula.james@hull.com`, and no email with "Ursula James" in `body_text`.'
    iw fail msg: "FAIL - Found offending emails: Email index 2 (subject: Contractual Rate Dispute — Hull Insurance / A4789P / CPT 11241, folder: Drafts) has to_addr='ursula.james@hull.com'. Email index 2 (subject: Contractual Rate Dispute"
- [rubric_1] opus 2/4 haiku 0/4 iw 0/4 | expected_output | RUBRIC: '`calendar_data.json` has exactly 10 events.'
    iw fail msg: 'Expected exactly 10 events in calendar_data.json, but found 11.'
- [rubric_1] opus 3/4 haiku 1/4 iw 3/4 | expected_output | RUBRIC: '`mailbox.json` must contain exactly 1 email in inbox, 2 emails in sent, and 1 email in drafts.'
    iw fail msg: 'FAIL. Found: inbox=1, sent=2, drafts=2. Expected: inbox=1, sent=2, drafts=1.'

## medical_pathfinder_billing_and_coding_1d8667fc
- [495d3ee8] opus 4/4 haiku 0/4 iw 0/4 | expected_output | RUBRIC: "In file `PBC_Claim_Register.xlsx`, cells for CLM-1008 (Harold Jensen) in row 9 must have: M9=210.00 (Allowed Amount), N9=180.00 (Paid Amount), O9=70.00 (Contractual Adj), P9=30.00 (Patient Rep), Q9='Paid - Full' (Claim Status), R9='Posted' (Payment Posting Sta"
    iw fail msg: 'CLM-1008 (Harold Jensen) row 9 issues in PBC_Claim_Register.xlsx: M9 (Allowed Amount) expected 210.00, got None'
- [b1182ec4] opus 1/4 haiku 0/4 iw 0/4 | expected_output | RUBRIC: "In file `PBC_Claim_Register.xlsx`, cells for CLM-1033 (Elaine Foster) in row 34 must have: M34=165.00 (Allowed Amount), N34=142.00 (Paid Amount), O34=58.00 (Contractual Adj), P34=20.00 (Patient Rep), Q34='Written Off' (Claim Status), R34='Posted' (Payment Post"
    iw fail msg: 'CLM-1033 (Elaine Foster) row 34 issues in PBC_Claim_Register.xlsx: M34 (Allowed Amount) expected 165.00, got None; N34 (Paid Amount) expected 142.00, got None; O34 (Contractual Adj) expected 58.00, got None; P34 (Patient'

## medical_pathfinder_billing_and_coding_9d274282
- [3bdc1b19] opus 1/4 haiku 0/4 iw 0/1 | expected_output | RUBRIC: 'In file `PBC_Claim_Register.xlsx` in any sheet, rows with the following "Claim ID" must each have Claim Status as \'Paid - Full\' and Payment Posting Status as \'Posted\' CLM-10042, CLM-10047, CLM-10051, CLM-10058, CLM-10061, CLM-10071, and CLM-10082.'
    iw fail msg: "Failed checks (4 issues): CLM-10071: Claim Status is 'In Recovery' (expected 'Paid - Full') [file=PBC_Claim_Register.xlsx, sheet=Claim Register]; CLM-10071: Payment Posting Status is '' (expected 'Posted') [file=PBC_Clai"
- [51b86ff0] opus 1/4 haiku 0/4 iw 0/1 | expected_output | RUBRIC: 'In file `PBC_Claim_Register.xlsx` in any sheet, the "Paid Amount" column for for each "Claim ID" must be: CLM-10042 ($247.50), CLM-10047 ($180.00), CLM-10051 ($315.00), CLM-10058 ($92.00), CLM-10061 ($410.00), CLM-10071 ($900.00), CLM-10082 ($650.00)'
    iw fail msg: 'Paid Amount mismatches: CLM-10071: Paid Amount is 0.0 (expected 900.0); CLM-10082: Paid Amount is 0.0 (expected 650.0)'

## medical_pathfinder_billing_and_coding_a70deabc
- [64b4e574] opus 1/4 haiku 0/4 iw 0/4 | expected_output | RUBRIC: "In file `PBC_Claim_Register.xlsx`, cell N14 must contain 'Written Off - RA Approved', cell N12 must contain 'Written Off', cell J12 must contain 175.25, cell L12 must contain 0, cell J14 must contain 816.5, cell L14 must contain 0, and cell N13 must contain 'I"
    iw fail msg: 'J14 expected 816.5 but got 920; L14 expected 0 but got 103.5 in PBC_Claim_Register.xlsx'
- [6bc193bb] opus 0/4 haiku 0/4 iw 0/4 | expected_output | RUBRIC: "In calendar_data.json, there must be exactly 15 calendar events total, and one event must have summary 'RCM Manager - Claim ID: CLM-2026-0048; Reason: Payer Dispute; Escalation Category: Operational' with start time of 3:15 PM on February 16, 2026, and an end "
    iw fail msg: 'Event end time "{\'dateTime\': \'2026-02-16T15:16:00-06:00\', \'timeZone\': \'America/Chicago\'}" does not clearly indicate 3:15 PM'

## medical_pathfinder_billing_and_coding_bbf1a560
- [a7957495] opus 0/4 haiku 1/4 iw 1/4 | expected_output | RUBRIC: "In `PBC_Escalation_Log.xlsx`, cells row 3 through 8 must each contain 'Financial' as their Category, and 'Escalated to RCM Manager - 2026-04-09' as their Resolution_Tkg."
    iw fail msg: "Failures found: Row 3 Category (col 3)='Operational', expected 'Financial'; Row 4 Category (col 3)='Operational', expected 'Financial'; Row 5 Category (col 3)='Operational', expected 'Financial'; Row 6 Category (col 3)='"
- [963d503e] opus 0/4 haiku 3/4 iw 1/4 | expected_output | RUBRIC: "In `slack_data.json`, channel C001 must contain a message with text 'Escalation: 2026-04-09. Category: Financial. Payer: Bullion Gold Insurance.'"
    iw fail msg: 'No message matching \'Escalation: 2026-04-09. Category: Financial. Payer: Bullion Gold Insurance.\' found in C001. Messages found: ["Majestic\'s system is down &amp; estimated to be back up earliest by 6pm today. 837P saved'
- [c8a402ed] opus 1/4 haiku 3/4 iw 2/4 | expected_output | RUBRIC: "In `mailbox.json`, one draft email must be addressed to popler.wen@bulliongoldinsurance.com with mayj@pathfinder.com as BCC, contain 'overpayment'/'overpaid', 're-classed', 'unpaid claims', 'same patient', 'refund', 'subject to approval', 'updates', and claim "
    iw fail msg: 'Draft email to payer failed checks: ["Missing \'subject to approval\'"]'

## medical_pathfinder_billing_and_coding_c01deb6e
- [rubric_1] opus 0/4 haiku 2/4 iw 0/4 | expected_output | RUBRIC: 'In `PBC_Denial_Worklist.xlsx`, Row 9, 10, or 11 must contain the following exact values: "DEN-2026-0030" (where 30 can be 29 or 38), "CLM-2026-0967", "PAT-1063", "Robert Daniels", "03/08/2026", "BlueCross TX", "CO-45", "N130", "Contractual/Payer Error", "Appea'
    iw fail msg: "No matching row found. Valid DEN IDs: ['den-2026-0029', 'den-2026-0030', 'den-2026-0038', 'den-2026-0039']. Expected remaining values: ['CLM-2026-0967', 'PAT-1063', 'Robert Daniels', '03/08/2026', 'BlueCross TX', 'CO-45'"
- [rubric_1] opus 3/4 haiku 3/4 iw 0/4 | expected_output | RUBRIC: 'In `PBC_RA_Queue.xlsx`, Row 9, 10, or 11 must contain the exact values: "RA-2026-0033" (where 33 can be 32 or 31), "04/24/2026", "CLM-2026-0967", "PAT-1063", "ERA Processing", [Any priority value is acceptable], "Maria Santos", "Open", and a BLANK cell (in the'
    iw fail msg: "No matching row found in rows 9-11 of PBC_RA_Queue.xlsx. Expected: RA-2026-003[1-3], 04/24/2026, CLM-2026-0967, PAT-1063, ERA Processing, [Any Priority], Maria Santos, Open, BLANK. Actual rows: Row 9: ['RA-2026-0031', '0"
- [rubric_1] opus 0/4 haiku 0/4 iw 1/4 | expected_output | RUBRIC: 'In `PBC_Claim_Register.xlsx`, there must be one row in the table with the following exact values: "CLM-2026-0892", "PAT-1042", "Michael Torres", "03/15/2026", "Dr. Sarah Chen", "1234567890", "1122334455", "BlueCross TX", "BCTX1", "99214", "E11.65", BLANK, "1",'
    iw fail msg: "Best partial match at row 33: 21/23 values matched. Mismatches: col 15: expected 'Resubmitted' got 'Denied'; col 23: expected 'N382' got 'None'"
- [rubric_1] opus 0/4 haiku 0/4 iw 1/4 | expected_output | RUBRIC: 'In `PBC_Claim_Register.xlsx`, there must be one row in the table with the following exact values [No partial matches acceptable, must match every value]: "CLM-2026-1105", "PAT-1058", "Linda Park", "03/20/2026", "Dr. James Miller", "2345678901", BLANK, "BlueCro'
    iw fail msg: "Required row not found in PBC_Claim_Register.xlsx. Found CLM-2026-1105 in sheet 'Claim Register' row 36, but values didn't fully match (20/23 matched). Mismatches: [(14, 'Resubmitted', 'Denied'), (21, 'CO-97', None), (22"
- [rubric_1] opus 1/4 haiku 0/4 iw 1/4 | expected_output | RUBRIC: 'In `PBC_Denial_Worklist.xlsx`, Row 9, 10, or 11 must contain the exact values: "DEN-2026-0028" (where 28 can be 29 or 30), "CLM-2026-0892", "PAT-1042", "Michael Torres", "03/15/2026", "BlueCross TX", "CO-16", "N382", "Technical/Administrative", "Correct and Re'
    iw fail msg: 'Expected values not found in PBC_Denial_Worklist.xlsx. Row contents (rows 9-11): Row 9: ["\'DEN-2026-0028\'", "\'CLM-2026-0892\'", "\'PAT-1042\'", "\'Michael Torres\'", "\'03/15/2026\'", "\'BlueCross TX\'", "\'CO-16\'", "\'N382\'", "\'Te'
- [rubric_1] opus 2/4 haiku 3/4 iw 2/4 | expected_output | RUBRIC: 'In `PBC_Claim_Register.xlsx`, there must be one row in the table with the exact values [No partial matches acceptable, must match every value]: "CLM-2026-0967", "PAT-1063", "Robert Daniels", "03/08/2026", "Dr. Amanda Foster", "3456789012", BLANK, "BlueCross TX'
    iw fail msg: "Row for CLM-2026-0967 found at row 29 but only 21/23 values match. Mismatches: col 21: expected='CO-45' got='None'; col 22: expected='N130' got='None'"
- [rubric_1] opus 3/4 haiku 3/4 iw 2/4 | expected_output | RUBRIC: 'In `PBC_RA_Queue.xlsx`, Row 9, 10, or 11 must contain the exact values: "RA-2026-0031" (where 31 can be 32 or 33), "04/24/2026", "CLM-2026-0892", "PAT-1042", "ERA Processing", [Any priority value is acceptable], "Maria Santos", "Resolved", "04/24/2026". (where'
    iw fail msg: "No row contains all expected core values. Expected RA ID in ['ra-2026-0031', 'ra-2026-0032', 'ra-2026-0033'], plus ['04/24/2026', 'CLM-2026-0892', 'PAT-1042', 'ERA Processing', 'Maria Santos']. Best match had 5/6 values "
- [rubric_1] opus 3/4 haiku 3/4 iw 2/4 | expected_output | RUBRIC: 'In `PBC_RA_Queue.xlsx`, row 9, 10, or 11 must contain the exact values: "RA-2026-0032" (where 32 can be 31 or 33), "04/24/2026", "CLM-2026-1105", "PAT-1058", "ERA Processing", [Any priority value is acceptable], "Maria Santos", "Resolved", "04/24/2026". (where'
    iw fail msg: "Expected values not found in rows 8-12 of PBC_RA_Queue.xlsx. Expected RA ID: RA-2026-0031/32/33 Expected core: ['04/24/2026', 'CLM-2026-1105', 'PAT-1058', 'ERA Processing', 'Maria Santos'] Status: 'Resolved', 'Open', or "
- [rubric_1] opus 3/4 haiku 2/4 iw 3/4 | expected_output | RUBRIC: 'In `PBC_Escalation_Log.xlsx`, Row 4 or 5 must contain the following exact values: "ESC-2026-0008" (or "ESC-2026-0009"), "04/24/2026", "CLM-2026-0234, CLM-2026-0356, CLM-2026-0489, CLM-2026-0612, CLM-2026-0892" (in any order), "Operational", "Pattern Recurrence'
    iw fail msg: "Row 5: 7/8 checks passed. Details: Found valid ESC ID; Found date 04/24/2026; Found all 5 claims; Found 'Operational'; Found 'Pattern Recurrence'; Found 'Maria Santos'; Found 'David Park'; Missing 'Open'; Found blank cel"
- [rubric_1] opus 2/4 haiku 4/4 iw 3/4 | expected_output | RUBRIC: 'In `PBC_Escalation_Log.xlsx`, Row 4 or 5 must contain the exact values: "ESC-2026-0009" (or "ESC-2026-0008"), "04/24/2026", "CLM-2026-0967", "Financial", "Payer Dispute", "Maria Santos", "David Park", "Open", and BLANK (empty cell).'
    iw fail msg: "No row (4-10) in PBC_Escalation_Log.xlsx contains the expected escalation entry. Expected ESC-2026-0008/0009, 04/24/2026, CLM-2026-0967, Financial, Payer Dispute, Maria Santos, David Park, Open. Found rows: Row 4: ['ESC-"

## medical_pathfinder_billing_and_coding_ec505b6b
- [c65cec1b] opus 4/4 haiku 1/4 iw 1/4 | expected_output | RUBRIC: 'In `mailbox.json` (external services), the body of the sent appeal email to appeals@aetna-sim.com must include a claim reference block with all six required fields in order — Claim ID: CLM-2026-00001, Patient ID, DOS, CPT Code(s), Payer, and Claim Status — for'
    iw fail msg: "Appeal email body missing required claim reference fields: ['cpt\\\\s*code\\\\(?s\\\\)?\\\\s*:']"