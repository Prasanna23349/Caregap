// ============================================================
// BCS CARE GAP — NEO4J LOAD SCRIPT
// Step 1: Load All 30 Members into Knowledge Graph
// Source: Scenario_2_care_gap_multi_measure_dataset.xlsx
// Measurement Year: 2026 | Measure: BCS (Hopkins BCS-E)
// Lookback Window: 2024-10-01 → 2026-12-31 (27 months)
// Proactive Window: 18 months before lookback end
// ============================================================


// ============================================================
// SECTION 0: CONSTRAINTS & INDEXES
// Run these first before loading any data
// ============================================================

CREATE CONSTRAINT member_id IF NOT EXISTS
FOR (m:Member) REQUIRE m.memberID IS UNIQUE;

CREATE CONSTRAINT provider_id IF NOT EXISTS
FOR (p:Provider) REQUIRE p.providerID IS UNIQUE;

CREATE CONSTRAINT plan_id IF NOT EXISTS
FOR (bp:BenefitPlan) REQUIRE bp.planID IS UNIQUE;

CREATE CONSTRAINT claim_id IF NOT EXISTS
FOR (c:Claim) REQUIRE c.claimID IS UNIQUE;

CREATE CONSTRAINT measure_id IF NOT EXISTS
FOR (qm:QualityMeasure) REQUIRE qm.measureID IS UNIQUE;

CREATE CONSTRAINT caregap_id IF NOT EXISTS
FOR (cg:CareGap) REQUIRE cg.careGapID IS UNIQUE;

CREATE CONSTRAINT outreach_id IF NOT EXISTS
FOR (o:Outreach) REQUIRE o.outreachID IS UNIQUE;

CREATE INDEX member_name IF NOT EXISTS
FOR (m:Member) ON (m.fullName);

CREATE INDEX claim_cpt IF NOT EXISTS
FOR (c:Claim) ON (c.cptCode);

CREATE INDEX screening_date IF NOT EXISTS
FOR (sh:ScreeningHistory) ON (sh.lastMammogramDate);


// ============================================================
// SECTION 1: SHARED NODES
// Create once — reused by all members
// ============================================================

// --- 1A: Benefit Plan ---
MERGE (bp:BenefitPlan {planID: 'PL-001'})
SET bp.planType                 = 'Commercial PPO',
    bp.payerName                = 'Hopkins Health Plans',
    bp.preventiveServicesCovered = ['Mammography','Colonoscopy','Cervical Cytology','HPV','HbA1c','Adult Immunizations'],
    bp.mammogramCoverage        = '100% Preventive',
    bp.copay                    = 0.00,
    bp.deductible               = 500.00,
    bp.eligibilityRules         = 'Active enrollment, Age/Gender/Diagnosis per measure';

// --- 1B: Quality Measure — BCS Only ---
MERGE (qm:QualityMeasure {measureID: 'BCS'})
SET qm.measureName              = 'Breast Cancer Screening',
    qm.measureSource            = 'Hopkins HEDIS BCS-E',
    qm.ageEligibilityMin        = 42,
    qm.ageEligibilityMax        = 74,
    qm.lookbackAgeMin           = 40,
    qm.genderRequirement        = 'Female',
    qm.measureLookbackMonths    = 24,
    qm.proactiveLookbackMonths  = 18,
    qm.measureWindowStart       = date('2024-10-01'),
    qm.measureWindowEnd         = date('2026-12-31'),
    qm.proactiveWindowStart     = date('2025-06-01'),
    qm.validCPTCodes            = ['77067','77066','77065','77062','77061','77063'],
    qm.cpt77063StandaloneValid  = false,
    qm.mriAcceptable            = false,
    qm.ultrasoundAcceptable     = false,
    qm.biopsyAcceptable         = false,
    qm.cadAloneAcceptable       = false,
    qm.referenceURL             = 'https://www.hopkinsmedicine.org/-/media/johns-hopkins-health-plans/documents/2025-hedis-quality-measures-tip-sheet.pdf';

// --- 1C: Providers (P1000–P1017) ---
MERGE (p:Provider {providerID: 'P1000'})
SET p.providerName='Dr. Riley Kim', p.specialty='Internal Medicine',
    p.facilityType='Clinic', p.networkStatus='In-Network', p.state='GA';

MERGE (p:Provider {providerID: 'P1001'})
SET p.providerName='Dr. Hayden Park', p.specialty='Internal Medicine',
    p.facilityType='Clinic', p.networkStatus='In-Network', p.state='NY';

MERGE (p:Provider {providerID: 'P1002'})
SET p.providerName='Dr. Logan Rivera', p.specialty='Internal Medicine',
    p.facilityType='Clinic', p.networkStatus='In-Network', p.state='TX';

MERGE (p:Provider {providerID: 'P1003'})
SET p.providerName='Dr. Skyler ONeal', p.specialty='Family Medicine',
    p.facilityType='Clinic', p.networkStatus='In-Network', p.state='OH';

MERGE (p:Provider {providerID: 'P1004'})
SET p.providerName='Dr. Emery Fox', p.specialty='Internal Medicine',
    p.facilityType='Clinic', p.networkStatus='In-Network', p.state='NC';

MERGE (p:Provider {providerID: 'P1005'})
SET p.providerName='Dr. Kai Iyer', p.specialty='Internal Medicine',
    p.facilityType='Clinic', p.networkStatus='In-Network', p.state='MA';

MERGE (p:Provider {providerID: 'P1006'})
SET p.providerName='Dr. Devon Desai', p.specialty='Family Medicine',
    p.facilityType='Clinic', p.networkStatus='In-Network', p.state='GA';

MERGE (p:Provider {providerID: 'P1007'})
SET p.providerName='Dr. Avery ONeal', p.specialty='Family Medicine',
    p.facilityType='Clinic', p.networkStatus='In-Network', p.state='WA';

MERGE (p:Provider {providerID: 'P1008'})
SET p.providerName='Dr. Taylor Lee', p.specialty='Internal Medicine',
    p.facilityType='Clinic', p.networkStatus='In-Network', p.state='AZ';

MERGE (p:Provider {providerID: 'P1009'})
SET p.providerName='Dr. Harper Collins', p.specialty='Family Medicine',
    p.facilityType='Clinic', p.networkStatus='In-Network', p.state='VA';

MERGE (p:Provider {providerID: 'P1010'})
SET p.providerName='Dr. Sage Alvarez', p.specialty='Internal Medicine',
    p.facilityType='Clinic', p.networkStatus='In-Network', p.state='FL';

MERGE (p:Provider {providerID: 'P1011'})
SET p.providerName='Dr. Logan Rivera', p.specialty='Family Medicine',
    p.facilityType='Clinic', p.networkStatus='In-Network', p.state='VA';

MERGE (p:Provider {providerID: 'P1012'})
SET p.providerName='Dr. Rowan Reese', p.specialty='OB/GYN',
    p.facilityType='Clinic', p.networkStatus='In-Network', p.state='PA';

MERGE (p:Provider {providerID: 'P1013'})
SET p.providerName='Dr. Logan Shah', p.specialty='Endocrinology',
    p.facilityType='Clinic', p.networkStatus='In-Network', p.state='PA';

MERGE (p:Provider {providerID: 'P1014'})
SET p.providerName='Dr. Casey ONeal', p.specialty='OB/GYN',
    p.facilityType='Clinic', p.networkStatus='In-Network', p.state='OH';

MERGE (p:Provider {providerID: 'P1015'})
SET p.providerName='Dr. Kendall Lee', p.specialty='Laboratory',
    p.facilityType='Lab', p.networkStatus='In-Network', p.state='FL';

MERGE (p:Provider {providerID: 'P1016'})
SET p.providerName='Dr. Morgan Alvarez', p.specialty='Radiology',
    p.facilityType='Imaging Center', p.networkStatus='In-Network', p.state='CA';

MERGE (p:Provider {providerID: 'P1017'})
SET p.providerName='Dr. Jamie Murphy', p.specialty='Radiology',
    p.facilityType='Imaging Center', p.networkStatus='In-Network', p.state='PA';


// ============================================================
// SECTION 2: MEMBERS + THEIR NODES
// 20-node structure per member
// Data from Excel — Clinical fields marked as PENDING
// ============================================================

// ============================================================
// MEMBER M0001 — Hayden Iyer
// Age: 34Y 8M | Gender: M | Not BCS Eligible (Male)
// ============================================================

MERGE (m:Member {memberID: 'M0001'})
SET m.fullName = 'Hayden Iyer';

MERGE (d:Demographics {demoID: 'DEMO-M0001'})
SET d.dateOfBirth           = date('1991-07-01'),
    d.age                   = 34,
    d.administrativeGender  = 'Male',
    d.zipCode               = '02116',
    d.state                 = 'MA',
    d.employmentStatus = 'Retired',
    d.healthLiteracyLevel = 'High';

MERGE (e:Enrollment {enrollmentID: 'ENR-M0001'})
SET e.enrollmentStartDate      = date('2026-01-01'),
    e.enrollmentEndDate        = date('2026-12-31'),
    e.continuouslyEnrolled     = true,
    e.enrollmentGapInPeriod    = false,
    e.measurementYear          = 2026,
    e.measureLookbackStart     = date('2024-10-01'),
    e.measureLookbackEnd       = date('2026-12-31'),
    e.proactiveLookbackStart   = date('2025-06-01'),
    e.disenrolled              = false,
    e.deceased                 = false;

MERGE (ep:ExclusionProfile {exclusionID: 'EXC-M0001'})
SET ep.bilateralMastectomy      = false,
    ep.hospice                  = false,
    ep.palliativeCare           = false,
    ep.frailty                  = false,
    ep.genderAffirmingSurgery   = false,
    ep.medicare66PlusInSNP_LTC  = false,
    ep.anyExclusionPresent      = false;

// BCS Eligibility: NOT ELIGIBLE — Male
MERGE (cg:CareGap {careGapID: 'GAP-BCS-M0001'})
SET cg.measureID    = 'BCS',
    cg.gapStatus    = 'NOT ELIGIBLE',
    cg.reason       = 'Male — Not in BCS measure';

MERGE (m:Member {memberID: 'M0001'})
MERGE (d:Demographics {demoID: 'DEMO-M0001'})
MERGE (e:Enrollment {enrollmentID: 'ENR-M0001'})
MERGE (ep:ExclusionProfile {exclusionID: 'EXC-M0001'})
MERGE (bp:BenefitPlan {planID: 'PL-001'})
MERGE (pcp:Provider {providerID: 'P1015'})
MERGE (cg:CareGap {careGapID: 'GAP-BCS-M0001'})
MERGE (m)-[:HAS_DEMOGRAPHICS]->(d)
MERGE (m)-[:HAS_ENROLLMENT]->(e)
MERGE (m)-[:HAS_EXCLUSION_PROFILE]->(ep)
MERGE (m)-[:ENROLLED_IN]->(bp)
MERGE (m)-[:HAS_PCP]->(pcp)
MERGE (m)-[:HAS_CARE_GAP]->(cg);


// ============================================================
// MEMBER M0002 — Taylor Zhang
// Age: 41Y 6M | Gender: M | Not BCS Eligible (Male)
// ============================================================

MERGE (m:Member {memberID: 'M0002'})
SET m.fullName = 'Taylor Zhang';

MERGE (d:Demographics {demoID: 'DEMO-M0002'})
SET d.dateOfBirth           = date('1984-09-07'),
    d.age                   = 41,
    d.administrativeGender  = 'Male',
    d.zipCode               = '22203',
    d.state                 = 'VA',
    d.employmentStatus = 'Employed',
    d.healthLiteracyLevel = 'Adequate';

MERGE (e:Enrollment {enrollmentID: 'ENR-M0002'})
SET e.enrollmentStartDate      = date('2026-01-01'),
    e.enrollmentEndDate        = date('2026-12-31'),
    e.continuouslyEnrolled     = true,
    e.enrollmentGapInPeriod    = false,
    e.measurementYear          = 2026,
    e.measureLookbackStart     = date('2024-10-01'),
    e.measureLookbackEnd       = date('2026-12-31'),
    e.proactiveLookbackStart   = date('2025-06-01'),
    e.disenrolled              = false,
    e.deceased                 = false;

MERGE (ep:ExclusionProfile {exclusionID: 'EXC-M0002'})
SET ep.bilateralMastectomy=false, ep.hospice=false, ep.palliativeCare=false,
    ep.frailty=false, ep.genderAffirmingSurgery=false,
    ep.medicare66PlusInSNP_LTC=false, ep.anyExclusionPresent=false;

MERGE (cg:CareGap {careGapID: 'GAP-BCS-M0002'})
SET cg.measureID='BCS', cg.gapStatus='NOT ELIGIBLE', cg.reason='Male — Not in BCS measure';

MERGE (m:Member {memberID: 'M0002'})
MERGE (d:Demographics {demoID: 'DEMO-M0002'})
MERGE (e:Enrollment {enrollmentID: 'ENR-M0002'})
MERGE (ep:ExclusionProfile {exclusionID: 'EXC-M0002'})
MERGE (bp:BenefitPlan {planID: 'PL-001'})
MERGE (pcp:Provider {providerID: 'P1006'})
MERGE (cg:CareGap {careGapID: 'GAP-BCS-M0002'})
MERGE (m)-[:HAS_DEMOGRAPHICS]->(d)
MERGE (m)-[:HAS_ENROLLMENT]->(e)
MERGE (m)-[:HAS_EXCLUSION_PROFILE]->(ep)
MERGE (m)-[:ENROLLED_IN]->(bp)
MERGE (m)-[:HAS_PCP]->(pcp)
MERGE (m)-[:HAS_CARE_GAP]->(cg);


// ============================================================
// MEMBER M0003 — Quinn Fox
// Age: 47Y 11M | Gender: M | Not BCS Eligible (Male)
// ============================================================

MERGE (m:Member {memberID: 'M0003'})
SET m.fullName = 'Quinn Fox';

MERGE (d:Demographics {demoID: 'DEMO-M0003'})
SET d.dateOfBirth='1978-04-01', d.age=47,
    d.administrativeGender='Male', d.zipCode='22203', d.state='VA',
    d.employmentStatus = 'Self-employed', d.healthLiteracyLevel = 'Marginal';

MERGE (e:Enrollment {enrollmentID: 'ENR-M0003'})
SET e.enrollmentStartDate=date('2026-01-01'), e.enrollmentEndDate=date('2026-12-31'),
    e.continuouslyEnrolled=true, e.enrollmentGapInPeriod=false,
    e.measurementYear=2026, e.measureLookbackStart=date('2024-10-01'),
    e.measureLookbackEnd=date('2026-12-31'), e.proactiveLookbackStart=date('2025-06-01'),
    e.disenrolled=false, e.deceased=false;

MERGE (ep:ExclusionProfile {exclusionID: 'EXC-M0003'})
SET ep.bilateralMastectomy=false, ep.hospice=false, ep.palliativeCare=false,
    ep.frailty=false, ep.genderAffirmingSurgery=false,
    ep.medicare66PlusInSNP_LTC=false, ep.anyExclusionPresent=false;

MERGE (cg:CareGap {careGapID: 'GAP-BCS-M0003'})
SET cg.measureID='BCS', cg.gapStatus='NOT ELIGIBLE', cg.reason='Male — Not in BCS measure';

MERGE (m:Member {memberID: 'M0003'})
MERGE (d:Demographics {demoID: 'DEMO-M0003'})
MERGE (e:Enrollment {enrollmentID: 'ENR-M0003'})
MERGE (ep:ExclusionProfile {exclusionID: 'EXC-M0003'})
MERGE (bp:BenefitPlan {planID: 'PL-001'})
MERGE (pcp:Provider {providerID: 'P1000'})
MERGE (cg:CareGap {careGapID: 'GAP-BCS-M0003'})
MERGE (m)-[:HAS_DEMOGRAPHICS]->(d)
MERGE (m)-[:HAS_ENROLLMENT]->(e)
MERGE (m)-[:HAS_EXCLUSION_PROFILE]->(ep)
MERGE (m)-[:ENROLLED_IN]->(bp)
MERGE (m)-[:HAS_PCP]->(pcp)
MERGE (m)-[:HAS_CARE_GAP]->(cg);


// ============================================================
// MEMBER M0004 — Alex Banerjee
// Age: 69Y 7M | Gender: F | BCS ELIGIBLE
// ============================================================

MERGE (m:Member {memberID: 'M0004'})
SET m.fullName = 'Alex Banerjee';

MERGE (d:Demographics {demoID: 'DEMO-M0004'})
SET d.dateOfBirth           = date('1956-08-25'),
    d.age                   = 69,
    d.administrativeGender  = 'Female',
    d.sexAssignedAtBirth    = 'Female',
    d.sexParamClinicalUse   = 'Female-typical',
    d.zipCode               = '94110',
    d.state                 = 'CA',
    d.employmentStatus = 'Employed',
    d.healthLiteracyLevel = 'Adequate';

MERGE (e:Enrollment {enrollmentID: 'ENR-M0004'})
SET e.enrollmentStartDate      = date('2026-01-01'),
    e.enrollmentEndDate        = date('2026-12-31'),
    e.continuouslyEnrolled     = true,
    e.enrollmentGapInPeriod    = false,
    e.measurementYear          = 2026,
    e.measureLookbackStart     = date('2024-10-01'),
    e.measureLookbackEnd       = date('2026-12-31'),
    e.proactiveLookbackStart   = date('2025-06-01'),
    e.disenrolled              = false,
    e.deceased                 = false;

// Age rule checks for BCS
MERGE (arc:AgeRuleCheck {ageRuleID: 'ARC-M0004'})
SET arc.eligibilityAgeCheck    = true,   // Age 69 — within 42-74
    arc.lookbackAgeCheck       = true,   // Will be 67+ at any mammogram in window
    arc.medicare66PlusInSNP_LTC= false;

MERGE (ep:ExclusionProfile {exclusionID: 'EXC-M0004'})
SET ep.bilateralMastectomy=false, ep.hospice=false, ep.palliativeCare=false,
    ep.frailty=false, ep.genderAffirmingSurgery=false,
    ep.medicare66PlusInSNP_LTC=false, ep.anyExclusionPresent=false;

// Vitals — PENDING from EHR
MERGE (v:Vitals {vitalsID: 'VIT-M0004'})
SET v.status='PENDING — Awaiting EHR Data';

// Clinical History — PENDING from EHR
MERGE (ch:ClinicalHistory {historyID: 'CLH-M0004'})
SET ch.status='PENDING — Awaiting EHR Data';

// Screening History — No BCS mammogram claim found in data
MERGE (sh:ScreeningHistory {screeningID: 'SCR-M0004'})
SET sh.lastMammogramDate       = null,
    sh.mammogramType           = 'None found in claims',
    sh.fallsInLookbackWindow   = false,
    sh.screeningStatus         = 'No mammogram claim found';

// Care Gap — Open (no mammogram in claims)
MERGE (cg:CareGap {careGapID: 'GAP-BCS-M0004'})
SET cg.measureID       = 'BCS',
    cg.gapStatus       = 'OPEN',
    cg.gapCreatedDate  = date('2026-01-01'),
    cg.priorityLevel   = 'UNASSIGNED',
    cg.reason          = 'No BCS mammogram claim found in measurement window';

// SDOH — PENDING
MERGE (sd:SDOH {sdohID: 'SDOH-M0004'})
SET sd.status='PENDING — Awaiting member data';

// Consent — PENDING
MERGE (con:Consent {consentID: 'CON-M0004'})
SET con.optOutOfOutreach=false, con.hipaaConsentOnFile=true,
    con.communicationConsent=['SMS','Phone'];

MERGE (m:Member {memberID: 'M0004'})
MERGE (d:Demographics {demoID: 'DEMO-M0004'})
MERGE (e:Enrollment {enrollmentID: 'ENR-M0004'})
MERGE (arc:AgeRuleCheck {ageRuleID: 'ARC-M0004'})
MERGE (ep:ExclusionProfile {exclusionID: 'EXC-M0004'})
MERGE (v:Vitals {vitalsID: 'VIT-M0004'})
MERGE (ch:ClinicalHistory {historyID: 'CLH-M0004'})
MERGE (sh:ScreeningHistory {screeningID: 'SCR-M0004'})
MERGE (cg:CareGap {careGapID: 'GAP-BCS-M0004'})
MERGE (sd:SDOH {sdohID: 'SDOH-M0004'})
MERGE (con:Consent {consentID: 'CON-M0004'})
MERGE (bp:BenefitPlan {planID: 'PL-001'})
MERGE (pcp:Provider {providerID: 'P1004'})
MERGE (qm:QualityMeasure {measureID: 'BCS'})
MERGE (m)-[:HAS_DEMOGRAPHICS]->(d)
MERGE (m)-[:HAS_ENROLLMENT]->(e)
MERGE (m)-[:HAS_AGE_RULE_CHECK]->(arc)
MERGE (m)-[:HAS_EXCLUSION_PROFILE]->(ep)
MERGE (m)-[:HAS_VITALS]->(v)
MERGE (m)-[:HAS_CLINICAL_HISTORY]->(ch)
MERGE (m)-[:HAS_SCREENING_HISTORY]->(sh)
MERGE (m)-[:HAS_CARE_GAP]->(cg)
MERGE (m)-[:HAS_SDOH]->(sd)
MERGE (m)-[:HAS_CONSENT]->(con)
MERGE (m)-[:ENROLLED_IN]->(bp)
MERGE (m)-[:HAS_PCP]->(pcp)
MERGE (cg)-[:TRACKED_UNDER]->(qm);


// ============================================================
// MEMBER M0005 — Rowan Kim
// Age: 58Y 9M | Gender: M | Not BCS Eligible (Male)
// ============================================================

MERGE (m:Member {memberID: 'M0005'}) SET m.fullName='Rowan Kim';
MERGE (d:Demographics {demoID: 'DEMO-M0005'})
SET d.dateOfBirth=date('1967-06-07'), d.age=58,
    d.administrativeGender='Male', d.zipCode='43215', d.state='OH',
    d.employmentStatus = 'Unemployed', d.healthLiteracyLevel = 'High';
MERGE (e:Enrollment {enrollmentID: 'ENR-M0005'})
SET e.enrollmentStartDate=date('2026-01-01'), e.enrollmentEndDate=date('2026-12-31'),
    e.continuouslyEnrolled=true, e.measurementYear=2026,
    e.measureLookbackStart=date('2024-10-01'), e.measureLookbackEnd=date('2026-12-31'),
    e.proactiveLookbackStart=date('2025-06-01'), e.disenrolled=false, e.deceased=false;
MERGE (ep:ExclusionProfile {exclusionID: 'EXC-M0005'})
SET ep.bilateralMastectomy=false, ep.anyExclusionPresent=false;
MERGE (cg:CareGap {careGapID: 'GAP-BCS-M0005'})
SET cg.measureID='BCS', cg.gapStatus='NOT ELIGIBLE', cg.reason='Male — Not in BCS measure';
MERGE (m:Member {memberID: 'M0005'})
MERGE (d:Demographics {demoID: 'DEMO-M0005'})
MERGE (e:Enrollment {enrollmentID: 'ENR-M0005'})
MERGE (ep:ExclusionProfile {exclusionID: 'EXC-M0005'})
MERGE (pcp:Provider {providerID: 'P1010'})
MERGE (bp:BenefitPlan {planID: 'PL-001'})
MERGE (cg:CareGap {careGapID: 'GAP-BCS-M0005'})
MERGE (m)-[:HAS_DEMOGRAPHICS]->(d)
MERGE (m)-[:HAS_ENROLLMENT]->(e)
MERGE (m)-[:HAS_EXCLUSION_PROFILE]->(ep)
MERGE (m)-[:ENROLLED_IN]->(bp)
MERGE (m)-[:HAS_PCP]->(pcp)
MERGE (m)-[:HAS_CARE_GAP]->(cg);


// ============================================================
// MEMBER M0006 — Jamie Barrett
// Age: 63Y 4M | Gender: M | Not BCS Eligible (Male)
// Note: Has CPT 77067 claim — but Male, so excluded from BCS
// ============================================================

MERGE (m:Member {memberID: 'M0006'}) SET m.fullName='Jamie Barrett';
MERGE (d:Demographics {demoID: 'DEMO-M0006'})
SET d.dateOfBirth=date('1962-11-26'), d.age=63,
    d.administrativeGender='Male', d.zipCode='07030', d.state='NJ',
    d.employmentStatus = 'Employed', d.healthLiteracyLevel = 'Adequate';
MERGE (e:Enrollment {enrollmentID: 'ENR-M0006'})
SET e.enrollmentStartDate=date('2026-01-01'), e.enrollmentEndDate=date('2026-12-31'),
    e.continuouslyEnrolled=true, e.measurementYear=2026,
    e.measureLookbackStart=date('2024-10-01'), e.measureLookbackEnd=date('2026-12-31'),
    e.proactiveLookbackStart=date('2025-06-01'), e.disenrolled=false, e.deceased=false;
MERGE (ep:ExclusionProfile {exclusionID: 'EXC-M0006'})
SET ep.bilateralMastectomy=false, ep.anyExclusionPresent=false;
MERGE (cg:CareGap {careGapID: 'GAP-BCS-M0006'})
SET cg.measureID='BCS', cg.gapStatus='NOT ELIGIBLE', cg.reason='Male — Not in BCS measure';
MERGE (m:Member {memberID: 'M0006'})
MERGE (d:Demographics {demoID: 'DEMO-M0006'})
MERGE (e:Enrollment {enrollmentID: 'ENR-M0006'})
MERGE (ep:ExclusionProfile {exclusionID: 'EXC-M0006'})
MERGE (pcp:Provider {providerID: 'P1006'})
MERGE (bp:BenefitPlan {planID: 'PL-001'})
MERGE (cg:CareGap {careGapID: 'GAP-BCS-M0006'})
MERGE (m)-[:HAS_DEMOGRAPHICS]->(d)
MERGE (m)-[:HAS_ENROLLMENT]->(e)
MERGE (m)-[:HAS_EXCLUSION_PROFILE]->(ep)
MERGE (m)-[:ENROLLED_IN]->(bp)
MERGE (m)-[:HAS_PCP]->(pcp)
MERGE (m)-[:HAS_CARE_GAP]->(cg);


// ============================================================
// MEMBER M0007 — Jordan Lee
// Age: 35Y 5M | Gender: F | NOT ELIGIBLE — Age < 42
// ============================================================

MERGE (m:Member {memberID: 'M0007'}) SET m.fullName='Jordan Lee';
MERGE (d:Demographics {demoID: 'DEMO-M0007'})
SET d.dateOfBirth=date('1990-10-13'), d.age=35,
    d.administrativeGender='Female', d.sexAssignedAtBirth='Female',
    d.sexParamClinicalUse='Female-typical',
    d.zipCode='60601', d.state='IL',
    d.employmentStatus = 'Self-employed', d.healthLiteracyLevel = 'Adequate';
MERGE (e:Enrollment {enrollmentID: 'ENR-M0007'})
SET e.enrollmentStartDate=date('2026-01-01'), e.enrollmentEndDate=date('2026-12-31'),
    e.continuouslyEnrolled=true, e.measurementYear=2026,
    e.measureLookbackStart=date('2024-10-01'), e.measureLookbackEnd=date('2026-12-31'),
    e.proactiveLookbackStart=date('2025-06-01'), e.disenrolled=false, e.deceased=false;
MERGE (arc:AgeRuleCheck {ageRuleID: 'ARC-M0007'})
SET arc.eligibilityAgeCheck=false,  // Age 35 — below 42
    arc.lookbackAgeCheck=false,
    arc.medicare66PlusInSNP_LTC=false;
MERGE (ep:ExclusionProfile {exclusionID: 'EXC-M0007'})
SET ep.bilateralMastectomy=false, ep.anyExclusionPresent=false;
MERGE (cg:CareGap {careGapID: 'GAP-BCS-M0007'})
SET cg.measureID='BCS', cg.gapStatus='NOT ELIGIBLE',
    cg.reason='Age 35 — below BCS eligibility threshold of 42';
MERGE (m:Member {memberID: 'M0007'})
MERGE (d:Demographics {demoID: 'DEMO-M0007'})
MERGE (e:Enrollment {enrollmentID: 'ENR-M0007'})
MERGE (arc:AgeRuleCheck {ageRuleID: 'ARC-M0007'})
MERGE (ep:ExclusionProfile {exclusionID: 'EXC-M0007'})
MERGE (pcp:Provider {providerID: 'P1013'})
MERGE (bp:BenefitPlan {planID: 'PL-001'})
MERGE (cg:CareGap {careGapID: 'GAP-BCS-M0007'})
MERGE (m)-[:HAS_DEMOGRAPHICS]->(d)
MERGE (m)-[:HAS_ENROLLMENT]->(e)
MERGE (m)-[:HAS_AGE_RULE_CHECK]->(arc)
MERGE (m)-[:HAS_EXCLUSION_PROFILE]->(ep)
MERGE (m)-[:ENROLLED_IN]->(bp)
MERGE (m)-[:HAS_PCP]->(pcp)
MERGE (m)-[:HAS_CARE_GAP]->(cg);


// ============================================================
// MEMBER M0008 — Rowan Desai
// Age: 61Y 3M | Gender: F | BCS ELIGIBLE
// ============================================================

MERGE (m:Member {memberID: 'M0008'}) SET m.fullName='Rowan Desai';
MERGE (d:Demographics {demoID: 'DEMO-M0008'})
SET d.dateOfBirth=date('1964-12-20'), d.age=61,
    d.administrativeGender='Female', d.sexAssignedAtBirth='Female',
    d.sexParamClinicalUse='Female-typical',
    d.zipCode='30309', d.state='GA',
    d.employmentStatus = 'Self-employed', d.healthLiteracyLevel = 'Marginal';
MERGE (e:Enrollment {enrollmentID: 'ENR-M0008'})
SET e.enrollmentStartDate=date('2026-01-01'), e.enrollmentEndDate=date('2026-12-31'),
    e.continuouslyEnrolled=true, e.measurementYear=2026,
    e.measureLookbackStart=date('2024-10-01'), e.measureLookbackEnd=date('2026-12-31'),
    e.proactiveLookbackStart=date('2025-06-01'), e.disenrolled=false, e.deceased=false;
MERGE (arc:AgeRuleCheck {ageRuleID: 'ARC-M0008'})
SET arc.eligibilityAgeCheck=true,   // Age 61 — within 42-74
    arc.lookbackAgeCheck=true,
    arc.medicare66PlusInSNP_LTC=false;
MERGE (ep:ExclusionProfile {exclusionID: 'EXC-M0008'})
SET ep.bilateralMastectomy=false, ep.hospice=false, ep.palliativeCare=false,
    ep.frailty=false, ep.genderAffirmingSurgery=false,
    ep.medicare66PlusInSNP_LTC=false, ep.anyExclusionPresent=false;
MERGE (v:Vitals {vitalsID: 'VIT-M0008'}) SET v.status='UNASSIGNED';
MERGE (ch:ClinicalHistory {historyID: 'CLH-M0008'}) SET ch.status='UNASSIGNED';
MERGE (sh:ScreeningHistory {screeningID: 'SCR-M0008'})
SET sh.lastMammogramDate=null, sh.fallsInLookbackWindow=false,
    sh.screeningStatus='No mammogram claim found';
MERGE (cg:CareGap {careGapID: 'GAP-BCS-M0008'})
SET cg.measureID='BCS', cg.gapStatus='OPEN',
    cg.gapCreatedDate=date('2026-01-01'),
    cg.priorityLevel='UNASSIGNED',
    cg.reason='No BCS mammogram claim found';
MERGE (sd:SDOH {sdohID: 'SDOH-M0008'}) SET sd.status='UNASSIGNED';
MERGE (con:Consent {consentID: 'CON-M0008'})
SET con.optOutOfOutreach=false, con.hipaaConsentOnFile=true;
MERGE (m:Member {memberID: 'M0008'})
MERGE (d:Demographics {demoID: 'DEMO-M0008'})
MERGE (e:Enrollment {enrollmentID: 'ENR-M0008'})
MERGE (arc:AgeRuleCheck {ageRuleID: 'ARC-M0008'})
MERGE (ep:ExclusionProfile {exclusionID: 'EXC-M0008'})
MERGE (v:Vitals {vitalsID: 'VIT-M0008'})
MERGE (ch:ClinicalHistory {historyID: 'CLH-M0008'})
MERGE (sh:ScreeningHistory {screeningID: 'SCR-M0008'})
MERGE (cg:CareGap {careGapID: 'GAP-BCS-M0008'})
MERGE (sd:SDOH {sdohID: 'SDOH-M0008'})
MERGE (con:Consent {consentID: 'CON-M0008'})
MERGE (bp:BenefitPlan {planID: 'PL-001'})
MERGE (pcp:Provider {providerID: 'P1012'})
MERGE (qm:QualityMeasure {measureID: 'BCS'})
MERGE (m)-[:HAS_DEMOGRAPHICS]->(d)
MERGE (m)-[:HAS_ENROLLMENT]->(e)
MERGE (m)-[:HAS_AGE_RULE_CHECK]->(arc)
MERGE (m)-[:HAS_EXCLUSION_PROFILE]->(ep)
MERGE (m)-[:HAS_VITALS]->(v)
MERGE (m)-[:HAS_CLINICAL_HISTORY]->(ch)
MERGE (m)-[:HAS_SCREENING_HISTORY]->(sh)
MERGE (m)-[:HAS_CARE_GAP]->(cg)
MERGE (m)-[:HAS_SDOH]->(sd)
MERGE (m)-[:HAS_CONSENT]->(con)
MERGE (m)-[:ENROLLED_IN]->(bp)
MERGE (m)-[:HAS_PCP]->(pcp)
MERGE (cg)-[:TRACKED_UNDER]->(qm);


// ============================================================
// MEMBER M0009 — Quinn Gupta
// Age: 71Y 10M | Gender: F | BCS ELIGIBLE
// ============================================================

MERGE (m:Member {memberID: 'M0009'}) SET m.fullName='Quinn Gupta';
MERGE (d:Demographics {demoID: 'DEMO-M0009'})
SET d.dateOfBirth=date('1954-05-27'), d.age=71,
    d.administrativeGender='Female', d.sexAssignedAtBirth='Female',
    d.sexParamClinicalUse='Female-typical',
    d.zipCode='07030', d.state='NJ',
    d.employmentStatus = 'Employed', d.healthLiteracyLevel = 'Low';
MERGE (e:Enrollment {enrollmentID: 'ENR-M0009'})
SET e.enrollmentStartDate=date('2026-01-01'), e.enrollmentEndDate=date('2026-12-31'),
    e.continuouslyEnrolled=true, e.measurementYear=2026,
    e.measureLookbackStart=date('2024-10-01'), e.measureLookbackEnd=date('2026-12-31'),
    e.proactiveLookbackStart=date('2025-06-01'), e.disenrolled=false, e.deceased=false;
MERGE (arc:AgeRuleCheck {ageRuleID: 'ARC-M0009'})
SET arc.eligibilityAgeCheck=true,
    arc.lookbackAgeCheck=true,
    arc.medicare66PlusInSNP_LTC=false;
MERGE (ep:ExclusionProfile {exclusionID: 'EXC-M0009'})
SET ep.bilateralMastectomy=false, ep.hospice=false, ep.palliativeCare=false,
    ep.frailty=false, ep.genderAffirmingSurgery=false,
    ep.medicare66PlusInSNP_LTC=false, ep.anyExclusionPresent=false;
MERGE (v:Vitals {vitalsID: 'VIT-M0009'}) SET v.status='UNASSIGNED';
MERGE (ch:ClinicalHistory {historyID: 'CLH-M0009'}) SET ch.status='UNASSIGNED';
MERGE (sh:ScreeningHistory {screeningID: 'SCR-M0009'})
SET sh.lastMammogramDate=null, sh.fallsInLookbackWindow=false,
    sh.screeningStatus='No mammogram claim found — COL gap open (different measure)';
MERGE (cg:CareGap {careGapID: 'GAP-BCS-M0009'})
SET cg.measureID='BCS', cg.gapStatus='OPEN',
    cg.gapCreatedDate=date('2026-01-01'),
    cg.priorityLevel='UNASSIGNED',
    cg.reason='No BCS mammogram claim in window';
MERGE (sd:SDOH {sdohID: 'SDOH-M0009'}) SET sd.status='UNASSIGNED';
MERGE (con:Consent {consentID: 'CON-M0009'})
SET con.optOutOfOutreach=false, con.hipaaConsentOnFile=true;
MERGE (m:Member {memberID: 'M0009'})
MERGE (d:Demographics {demoID: 'DEMO-M0009'})
MERGE (e:Enrollment {enrollmentID: 'ENR-M0009'})
MERGE (arc:AgeRuleCheck {ageRuleID: 'ARC-M0009'})
MERGE (ep:ExclusionProfile {exclusionID: 'EXC-M0009'})
MERGE (v:Vitals {vitalsID: 'VIT-M0009'})
MERGE (ch:ClinicalHistory {historyID: 'CLH-M0009'})
MERGE (sh:ScreeningHistory {screeningID: 'SCR-M0009'})
MERGE (cg:CareGap {careGapID: 'GAP-BCS-M0009'})
MERGE (sd:SDOH {sdohID: 'SDOH-M0009'})
MERGE (con:Consent {consentID: 'CON-M0009'})
MERGE (bp:BenefitPlan {planID: 'PL-001'})
MERGE (pcp:Provider {providerID: 'P1003'})
MERGE (qm:QualityMeasure {measureID: 'BCS'})
MERGE (m)-[:HAS_DEMOGRAPHICS]->(d)
MERGE (m)-[:HAS_ENROLLMENT]->(e)
MERGE (m)-[:HAS_AGE_RULE_CHECK]->(arc)
MERGE (m)-[:HAS_EXCLUSION_PROFILE]->(ep)
MERGE (m)-[:HAS_VITALS]->(v)
MERGE (m)-[:HAS_CLINICAL_HISTORY]->(ch)
MERGE (m)-[:HAS_SCREENING_HISTORY]->(sh)
MERGE (m)-[:HAS_CARE_GAP]->(cg)
MERGE (m)-[:HAS_SDOH]->(sd)
MERGE (m)-[:HAS_CONSENT]->(con)
MERGE (m)-[:ENROLLED_IN]->(bp)
MERGE (m)-[:HAS_PCP]->(pcp)
MERGE (cg)-[:TRACKED_UNDER]->(qm);


// ============================================================
// MEMBER M0010 — Casey Lopez
// Age: 73Y 5M | Gender: F | BCS ELIGIBLE
// ============================================================

MERGE (m:Member {memberID: 'M0010'}) SET m.fullName='Casey Lopez';
MERGE (d:Demographics {demoID: 'DEMO-M0010'})
SET d.dateOfBirth=date('1952-10-04'), d.age=73,
    d.administrativeGender='Female', d.sexAssignedAtBirth='Female',
    d.sexParamClinicalUse='Female-typical',
    d.zipCode='28202', d.state='NC',
    d.employmentStatus = 'Employed', d.healthLiteracyLevel = 'Marginal';
MERGE (e:Enrollment {enrollmentID: 'ENR-M0010'})
SET e.enrollmentStartDate=date('2026-01-01'), e.enrollmentEndDate=date('2026-12-31'),
    e.continuouslyEnrolled=true, e.measurementYear=2026,
    e.measureLookbackStart=date('2024-10-01'), e.measureLookbackEnd=date('2026-12-31'),
    e.proactiveLookbackStart=date('2025-06-01'), e.disenrolled=false, e.deceased=false;
MERGE (arc:AgeRuleCheck {ageRuleID: 'ARC-M0010'})
SET arc.eligibilityAgeCheck=true,  // Age 73 — within 42-74
    arc.lookbackAgeCheck=true,
    arc.medicare66PlusInSNP_LTC=false;
MERGE (ep:ExclusionProfile {exclusionID: 'EXC-M0010'})
SET ep.bilateralMastectomy=false, ep.hospice=false, ep.palliativeCare=false,
    ep.frailty=false, ep.genderAffirmingSurgery=false,
    ep.medicare66PlusInSNP_LTC=false, ep.anyExclusionPresent=false;
MERGE (v:Vitals {vitalsID: 'VIT-M0010'}) SET v.status='UNASSIGNED';
MERGE (ch:ClinicalHistory {historyID: 'CLH-M0010'}) SET ch.status='UNASSIGNED';
MERGE (sh:ScreeningHistory {screeningID: 'SCR-M0010'})
SET sh.lastMammogramDate=null, sh.fallsInLookbackWindow=false,
    sh.screeningStatus='No mammogram claim found';
MERGE (cg:CareGap {careGapID: 'GAP-BCS-M0010'})
SET cg.measureID='BCS', cg.gapStatus='OPEN',
    cg.gapCreatedDate=date('2026-01-01'),
    cg.priorityLevel='UNASSIGNED',
    cg.reason='No BCS mammogram claim in window';
MERGE (sd:SDOH {sdohID: 'SDOH-M0010'}) SET sd.status='UNASSIGNED';
MERGE (con:Consent {consentID: 'CON-M0010'})
SET con.optOutOfOutreach=false, con.hipaaConsentOnFile=true;
MERGE (m:Member {memberID: 'M0010'})
MERGE (d:Demographics {demoID: 'DEMO-M0010'})
MERGE (e:Enrollment {enrollmentID: 'ENR-M0010'})
MERGE (arc:AgeRuleCheck {ageRuleID: 'ARC-M0010'})
MERGE (ep:ExclusionProfile {exclusionID: 'EXC-M0010'})
MERGE (v:Vitals {vitalsID: 'VIT-M0010'})
MERGE (ch:ClinicalHistory {historyID: 'CLH-M0010'})
MERGE (sh:ScreeningHistory {screeningID: 'SCR-M0010'})
MERGE (cg:CareGap {careGapID: 'GAP-BCS-M0010'})
MERGE (sd:SDOH {sdohID: 'SDOH-M0010'})
MERGE (con:Consent {consentID: 'CON-M0010'})
MERGE (bp:BenefitPlan {planID: 'PL-001'})
MERGE (pcp:Provider {providerID: 'P1009'})
MERGE (qm:QualityMeasure {measureID: 'BCS'})
MERGE (m)-[:HAS_DEMOGRAPHICS]->(d)
MERGE (m)-[:HAS_ENROLLMENT]->(e)
MERGE (m)-[:HAS_AGE_RULE_CHECK]->(arc)
MERGE (m)-[:HAS_EXCLUSION_PROFILE]->(ep)
MERGE (m)-[:HAS_VITALS]->(v)
MERGE (m)-[:HAS_CLINICAL_HISTORY]->(ch)
MERGE (m)-[:HAS_SCREENING_HISTORY]->(sh)
MERGE (m)-[:HAS_CARE_GAP]->(cg)
MERGE (m)-[:HAS_SDOH]->(sd)
MERGE (m)-[:HAS_CONSENT]->(con)
MERGE (m)-[:ENROLLED_IN]->(bp)
MERGE (m)-[:HAS_PCP]->(pcp)
MERGE (cg)-[:TRACKED_UNDER]->(qm);


// ============================================================
// MEMBER M0011 — Quinn Iyer *** KEY BCS MEMBER ***
// Age: 42Y 4M | Gender: F | BCS ELIGIBLE
// GAP STATUS: OPEN (from CareGaps_Dashboard)
// MAMMOGRAM: CPT 77067, Z12.31, Date: 2023-10-04 — 29 MONTHS AGO
// Falls OUTSIDE lookback window (window starts 2024-10-01)
// ============================================================

MERGE (m:Member {memberID: 'M0011'}) SET m.fullName='Quinn Iyer';
MERGE (d:Demographics {demoID: 'DEMO-M0011'})
SET d.dateOfBirth=date('1983-11-02'), d.age=42,
    d.administrativeGender='Female', d.sexAssignedAtBirth='Female',
    d.sexParamClinicalUse='Female-typical',
    d.zipCode='43215', d.state='OH',
    d.employmentStatus = 'Retired', d.healthLiteracyLevel = 'Low';
MERGE (e:Enrollment {enrollmentID: 'ENR-M0011'})
SET e.enrollmentStartDate=date('2026-01-01'), e.enrollmentEndDate=date('2026-12-31'),
    e.continuouslyEnrolled=true, e.measurementYear=2026,
    e.measureLookbackStart=date('2024-10-01'), e.measureLookbackEnd=date('2026-12-31'),
    e.proactiveLookbackStart=date('2025-06-01'), e.disenrolled=false, e.deceased=false;
MERGE (arc:AgeRuleCheck {ageRuleID: 'ARC-M0011'})
SET arc.eligibilityAgeCheck=true,  // Age 42 — exactly at threshold
    arc.lookbackAgeCheck=true,     // Was 40+ at mammogram date (2023-10-04, age 39... wait)
    // DOB: 1983-11-02, Mammogram: 2023-10-04
    // Age at mammogram = 39 years (birthday not yet in Oct 2023)
    // However guideline says 40+ at test date
    // NOTE: This is an edge case — age was 39 at mammogram
    // Will be flagged for review
    arc.ageAtLastMammogram=39,
    arc.lookbackAgeRuleNote='EDGE CASE — Age 39 at mammogram (2023-10-04) — below 40 threshold',
    arc.medicare66PlusInSNP_LTC=false;
MERGE (ep:ExclusionProfile {exclusionID: 'EXC-M0011'})
SET ep.bilateralMastectomy=false, ep.hospice=false, ep.palliativeCare=false,
    ep.frailty=false, ep.genderAffirmingSurgery=false,
    ep.medicare66PlusInSNP_LTC=false, ep.anyExclusionPresent=false;
MERGE (v:Vitals {vitalsID: 'VIT-M0011'}) SET v.status='UNASSIGNED';
MERGE (ch:ClinicalHistory {historyID: 'CLH-M0011'}) SET ch.status='UNASSIGNED';

// Screening History — Mammogram found but OUTSIDE window + age edge case
MERGE (sh:ScreeningHistory {screeningID: 'SCR-M0011'})
SET sh.lastMammogramDate       = date('2023-10-04'),
    sh.mammogramType           = 'Screening',
    sh.icd10Code               = 'Z12.31',
    sh.cptCode                 = '77067',
    sh.imagingType             = 'Bilateral Screening Mammography',
    sh.fallsInLookbackWindow   = false,
    sh.windowNote              = 'Date 2023-10-04 is BEFORE window start 2024-10-01',
    sh.ageAtMammogram          = 39,
    sh.ageRuleNote             = 'Age 39 at test — below 40 lookback threshold — REVIEW NEEDED',
    sh.monthsSinceLastScreen   = 29,
    sh.screeningStatus         = 'OVERDUE — Outside lookback window',
    sh.inNetworkFacility       = true,
    sh.hedisCompliant          = false;

MERGE (cg:CareGap {careGapID: 'GAP-BCS-M0011'})
SET cg.measureID       = 'BCS',
    cg.gapStatus       = 'OPEN',
    cg.gapCreatedDate  = date('2026-02-10'),
    cg.gapClosedDate   = null,
    cg.priorityLevel   = 'UNASSIGNED',
    cg.reason          = 'Mammogram 2023-10-04 outside window AND age 39 at test — both rules fail',
    cg.careManagerID   = 'CM-101';

MERGE (sd:SDOH {sdohID: 'SDOH-M0011'}) SET sd.status='UNASSIGNED';
MERGE (con:Consent {consentID: 'CON-M0011'})
SET con.optOutOfOutreach=false, con.hipaaConsentOnFile=true;

MERGE (m:Member {memberID: 'M0011'})
MERGE (d:Demographics {demoID: 'DEMO-M0011'})
MERGE (e:Enrollment {enrollmentID: 'ENR-M0011'})
MERGE (arc:AgeRuleCheck {ageRuleID: 'ARC-M0011'})
MERGE (ep:ExclusionProfile {exclusionID: 'EXC-M0011'})
MERGE (v:Vitals {vitalsID: 'VIT-M0011'})
MERGE (ch:ClinicalHistory {historyID: 'CLH-M0011'})
MERGE (sh:ScreeningHistory {screeningID: 'SCR-M0011'})
MERGE (cg:CareGap {careGapID: 'GAP-BCS-M0011'})
MERGE (sd:SDOH {sdohID: 'SDOH-M0011'})
MERGE (con:Consent {consentID: 'CON-M0011'})
MERGE (bp:BenefitPlan {planID: 'PL-001'})
MERGE (pcp:Provider {providerID: 'P1007'})
MERGE (qm:QualityMeasure {measureID: 'BCS'})
MERGE (m)-[:HAS_DEMOGRAPHICS]->(d)
MERGE (m)-[:HAS_ENROLLMENT]->(e)
MERGE (m)-[:HAS_AGE_RULE_CHECK]->(arc)
MERGE (m)-[:HAS_EXCLUSION_PROFILE]->(ep)
MERGE (m)-[:HAS_VITALS]->(v)
MERGE (m)-[:HAS_CLINICAL_HISTORY]->(ch)
MERGE (m)-[:HAS_SCREENING_HISTORY]->(sh)
MERGE (m)-[:HAS_CARE_GAP]->(cg)
MERGE (m)-[:HAS_SDOH]->(sd)
MERGE (m)-[:HAS_CONSENT]->(con)
MERGE (m)-[:ENROLLED_IN]->(bp)
MERGE (m)-[:HAS_PCP]->(pcp)
MERGE (cg)-[:TRACKED_UNDER]->(qm);


// ============================================================
// MEMBERS M0012–M0030 — Bulk Load Pattern
// Female eligible members get full 20-node structure
// Male/ineligible get minimal structure with NOT ELIGIBLE gap
// ============================================================

// M0012 — Lennox Singh | F | Age 41 | NOT ELIGIBLE (Age < 42)
MERGE (m:Member {memberID: 'M0012'}) SET m.fullName='Lennox Singh';
MERGE (d:Demographics {demoID: 'DEMO-M0012'})
SET d.dateOfBirth=date('1985-03-22'), d.age=41,
    d.administrativeGender='Female', d.sexAssignedAtBirth='Female',
    d.zipCode='77002', d.state='TX', d.employmentStatus = 'Unemployed';
MERGE (e:Enrollment {enrollmentID: 'ENR-M0012'})
SET e.enrollmentStartDate=date('2026-01-01'), e.enrollmentEndDate=date('2026-12-31'),
    e.continuouslyEnrolled=true, e.measurementYear=2026,
    e.measureLookbackStart=date('2024-10-01'), e.measureLookbackEnd=date('2026-12-31'),
    e.proactiveLookbackStart=date('2025-06-01'), e.disenrolled=false, e.deceased=false;
MERGE (arc:AgeRuleCheck {ageRuleID: 'ARC-M0012'})
SET arc.eligibilityAgeCheck=false, // Age 41 — just below 42
    arc.lookbackAgeCheck=false, arc.medicare66PlusInSNP_LTC=false;
MERGE (ep:ExclusionProfile {exclusionID: 'EXC-M0012'})
SET ep.bilateralMastectomy=false, ep.anyExclusionPresent=false;
MERGE (cg:CareGap {careGapID: 'GAP-BCS-M0012'})
SET cg.measureID='BCS', cg.gapStatus='NOT ELIGIBLE',
    cg.reason='Age 41 — below BCS eligibility threshold of 42';
MERGE (m:Member {memberID: 'M0012'})
MERGE (d:Demographics {demoID: 'DEMO-M0012'})
MERGE (e:Enrollment {enrollmentID: 'ENR-M0012'})
MERGE (arc:AgeRuleCheck {ageRuleID: 'ARC-M0012'})
MERGE (ep:ExclusionProfile {exclusionID: 'EXC-M0012'})
MERGE (cg:CareGap {careGapID: 'GAP-BCS-M0012'})
MERGE (bp:BenefitPlan {planID: 'PL-001'})
MERGE (pcp:Provider {providerID: 'P1000'})
MERGE (m)-[:HAS_DEMOGRAPHICS]->(d)
MERGE (m)-[:HAS_ENROLLMENT]->(e)
MERGE (m)-[:HAS_AGE_RULE_CHECK]->(arc)
MERGE (m)-[:HAS_EXCLUSION_PROFILE]->(ep)
MERGE (m)-[:ENROLLED_IN]->(bp)
MERGE (m)-[:HAS_PCP]->(pcp)
MERGE (m)-[:HAS_CARE_GAP]->(cg);

// M0013 — Cameron Desai | M | Age 36 | NOT ELIGIBLE (Male)
MERGE (m:Member {memberID: 'M0013'}) SET m.fullName='Cameron Desai';
MERGE (d:Demographics {demoID: 'DEMO-M0013'})
SET d.dateOfBirth=date('1990-03-07'), d.age=36,
    d.administrativeGender='Male', d.zipCode='02116', d.state='MA';
MERGE (e:Enrollment {enrollmentID: 'ENR-M0013'})
SET e.enrollmentStartDate=date('2026-01-01'), e.enrollmentEndDate=date('2026-12-31'),
    e.continuouslyEnrolled=true, e.measurementYear=2026,
    e.measureLookbackStart=date('2024-10-01'), e.measureLookbackEnd=date('2026-12-31'),
    e.proactiveLookbackStart=date('2025-06-01'), e.disenrolled=false, e.deceased=false;
MERGE (cg:CareGap {careGapID: 'GAP-BCS-M0013'})
SET cg.measureID='BCS', cg.gapStatus='NOT ELIGIBLE', cg.reason='Male';
MERGE (m:Member {memberID: 'M0013'})
MERGE (d:Demographics {demoID: 'DEMO-M0013'})
MERGE (e:Enrollment {enrollmentID: 'ENR-M0013'})
MERGE (cg:CareGap {careGapID: 'GAP-BCS-M0013'})
MERGE (bp:BenefitPlan {planID: 'PL-001'})
MERGE (pcp:Provider {providerID: 'P1000'})
MERGE (m)-[:HAS_DEMOGRAPHICS]->(d)
MERGE (m)-[:HAS_ENROLLMENT]->(e)
MERGE (m)-[:ENROLLED_IN]->(bp)
MERGE (m)-[:HAS_PCP]->(pcp)
MERGE (m)-[:HAS_CARE_GAP]->(cg);

// M0014 — Rowan Zhang | F | Age 39 | NOT ELIGIBLE (Age < 42)
MERGE (m:Member {memberID: 'M0014'}) SET m.fullName='Rowan Zhang';
MERGE (d:Demographics {demoID: 'DEMO-M0014'})
SET d.dateOfBirth=date('1986-08-10'), d.age=39,
    d.administrativeGender='Female', d.sexAssignedAtBirth='Female',
    d.zipCode='77002', d.state='TX';
MERGE (e:Enrollment {enrollmentID: 'ENR-M0014'})
SET e.enrollmentStartDate=date('2026-01-01'), e.enrollmentEndDate=date('2026-12-31'),
    e.continuouslyEnrolled=true, e.measurementYear=2026,
    e.measureLookbackStart=date('2024-10-01'), e.measureLookbackEnd=date('2026-12-31'),
    e.proactiveLookbackStart=date('2025-06-01'), e.disenrolled=false, e.deceased=false;
MERGE (arc:AgeRuleCheck {ageRuleID: 'ARC-M0014'})
SET arc.eligibilityAgeCheck=false, arc.lookbackAgeCheck=false,
    arc.medicare66PlusInSNP_LTC=false;
MERGE (cg:CareGap {careGapID: 'GAP-BCS-M0014'})
SET cg.measureID='BCS', cg.gapStatus='NOT ELIGIBLE', cg.reason='Age 39 — below 42 threshold';
MERGE (m:Member {memberID: 'M0014'})
MERGE (d:Demographics {demoID: 'DEMO-M0014'})
MERGE (e:Enrollment {enrollmentID: 'ENR-M0014'})
MERGE (arc:AgeRuleCheck {ageRuleID: 'ARC-M0014'})
MERGE (cg:CareGap {careGapID: 'GAP-BCS-M0014'})
MERGE (bp:BenefitPlan {planID: 'PL-001'})
MERGE (pcp:Provider {providerID: 'P1000'})
MERGE (m)-[:HAS_DEMOGRAPHICS]->(d)
MERGE (m)-[:HAS_ENROLLMENT]->(e)
MERGE (m)-[:HAS_AGE_RULE_CHECK]->(arc)
MERGE (m)-[:ENROLLED_IN]->(bp)
MERGE (m)-[:HAS_PCP]->(pcp)
MERGE (m)-[:HAS_CARE_GAP]->(cg);

// M0015 — Priya Gupta | F | Age 53 | BCS ELIGIBLE — No mammogram found
MERGE (m:Member {memberID: 'M0015'}) SET m.fullName='Priya Gupta';
MERGE (d:Demographics {demoID: 'DEMO-M0015'})
SET d.dateOfBirth=date('1972-05-02'), d.age=53,
    d.administrativeGender='Female', d.sexAssignedAtBirth='Female',
    d.sexParamClinicalUse='Female-typical',
    d.zipCode='60601', d.state='IL', d.employmentStatus = 'Retired';
MERGE (e:Enrollment {enrollmentID: 'ENR-M0015'})
SET e.enrollmentStartDate=date('2026-01-01'), e.enrollmentEndDate=date('2026-12-31'),
    e.continuouslyEnrolled=true, e.measurementYear=2026,
    e.measureLookbackStart=date('2024-10-01'), e.measureLookbackEnd=date('2026-12-31'),
    e.proactiveLookbackStart=date('2025-06-01'), e.disenrolled=false, e.deceased=false;
MERGE (arc:AgeRuleCheck {ageRuleID: 'ARC-M0015'})
SET arc.eligibilityAgeCheck=true, arc.lookbackAgeCheck=true,
    arc.medicare66PlusInSNP_LTC=false;
MERGE (ep:ExclusionProfile {exclusionID: 'EXC-M0015'})
SET ep.bilateralMastectomy=false, ep.anyExclusionPresent=false;
MERGE (v:Vitals {vitalsID: 'VIT-M0015'}) SET v.status='UNASSIGNED';
MERGE (ch:ClinicalHistory {historyID: 'CLH-M0015'}) SET ch.status='UNASSIGNED';
MERGE (sh:ScreeningHistory {screeningID: 'SCR-M0015'})
SET sh.lastMammogramDate=null, sh.fallsInLookbackWindow=false,
    sh.screeningStatus='No mammogram claim found';
MERGE (cg:CareGap {careGapID: 'GAP-BCS-M0015'})
SET cg.measureID='BCS', cg.gapStatus='OPEN',
    cg.gapCreatedDate=date('2026-01-01'),
    cg.priorityLevel='PENDING', cg.reason='No BCS mammogram claim found';
MERGE (sd:SDOH {sdohID: 'SDOH-M0015'}) SET sd.status='UNASSIGNED';
MERGE (con:Consent {consentID: 'CON-M0015'}) SET con.optOutOfOutreach=false;
MERGE (m:Member {memberID: 'M0015'})
MERGE (d:Demographics {demoID: 'DEMO-M0015'})
MERGE (e:Enrollment {enrollmentID: 'ENR-M0015'})
MERGE (arc:AgeRuleCheck {ageRuleID: 'ARC-M0015'})
MERGE (ep:ExclusionProfile {exclusionID: 'EXC-M0015'})
MERGE (v:Vitals {vitalsID: 'VIT-M0015'})
MERGE (ch:ClinicalHistory {historyID: 'CLH-M0015'})
MERGE (sh:ScreeningHistory {screeningID: 'SCR-M0015'})
MERGE (cg:CareGap {careGapID: 'GAP-BCS-M0015'})
MERGE (sd:SDOH {sdohID: 'SDOH-M0015'})
MERGE (con:Consent {consentID: 'CON-M0015'})
MERGE (bp:BenefitPlan {planID: 'PL-001'})
MERGE (pcp:Provider {providerID: 'P1011'})
MERGE (qm:QualityMeasure {measureID: 'BCS'})
MERGE (m)-[:HAS_DEMOGRAPHICS]->(d)
MERGE (m)-[:HAS_ENROLLMENT]->(e)
MERGE (m)-[:HAS_AGE_RULE_CHECK]->(arc)
MERGE (m)-[:HAS_EXCLUSION_PROFILE]->(ep)
MERGE (m)-[:HAS_VITALS]->(v)
MERGE (m)-[:HAS_CLINICAL_HISTORY]->(ch)
MERGE (m)-[:HAS_SCREENING_HISTORY]->(sh)
MERGE (m)-[:HAS_CARE_GAP]->(cg)
MERGE (m)-[:HAS_SDOH]->(sd)
MERGE (m)-[:HAS_CONSENT]->(con)
MERGE (m)-[:ENROLLED_IN]->(bp)
MERGE (m)-[:HAS_PCP]->(pcp)
MERGE (cg)-[:TRACKED_UNDER]->(qm);

// M0016 — Taylor Lopez | F | Age 28 | NOT ELIGIBLE (Age < 42)
// NOTE: GAP-BCS-2 CLOSED in dashboard — but she's 28, so this is a data anomaly
MERGE (m:Member {memberID: 'M0016'}) SET m.fullName='Taylor Lopez';
MERGE (d:Demographics {demoID: 'DEMO-M0016'})
SET d.dateOfBirth=date('1997-05-12'), d.age=28,
    d.administrativeGender='Female', d.sexAssignedAtBirth='Female',
    d.zipCode='28202', d.state='NC', d.employmentStatus = 'Retired';
MERGE (e:Enrollment {enrollmentID: 'ENR-M0016'})
SET e.enrollmentStartDate=date('2026-01-01'), e.enrollmentEndDate=date('2026-12-31'),
    e.continuouslyEnrolled=true, e.measurementYear=2026,
    e.measureLookbackStart=date('2024-10-01'), e.measureLookbackEnd=date('2026-12-31'),
    e.proactiveLookbackStart=date('2025-06-01'), e.disenrolled=false, e.deceased=false;
MERGE (arc:AgeRuleCheck {ageRuleID: 'ARC-M0016'})
SET arc.eligibilityAgeCheck=false,
    arc.lookbackAgeCheck=false,
    arc.medicare66PlusInSNP_LTC=false;
MERGE (cg:CareGap {careGapID: 'GAP-BCS-2'})
SET cg.measureID='BCS', cg.gapStatus='CLOSED',
    cg.gapCreatedDate=date('2026-01-22'), cg.gapClosedDate=date('2026-01-22'),
    cg.note='DATA ANOMALY — Member is 28 years old — below BCS eligibility — review needed';
MERGE (m:Member {memberID: 'M0016'})
MERGE (d:Demographics {demoID: 'DEMO-M0016'})
MERGE (e:Enrollment {enrollmentID: 'ENR-M0016'})
MERGE (arc:AgeRuleCheck {ageRuleID: 'ARC-M0016'})
MERGE (cg:CareGap {careGapID: 'GAP-BCS-2'})
MERGE (bp:BenefitPlan {planID: 'PL-001'})
MERGE (pcp:Provider {providerID: 'P1010'})
MERGE (m)-[:HAS_DEMOGRAPHICS]->(d)
MERGE (m)-[:HAS_ENROLLMENT]->(e)
MERGE (m)-[:HAS_AGE_RULE_CHECK]->(arc)
MERGE (m)-[:ENROLLED_IN]->(bp)
MERGE (m)-[:HAS_PCP]->(pcp)
MERGE (m)-[:HAS_CARE_GAP]->(cg);

// M0017 — Avery Reese | F | Age 54 | BCS ELIGIBLE — Mammogram found 2026-03-06
MERGE (m:Member {memberID: 'M0017'}) SET m.fullName='Avery Reese';
MERGE (d:Demographics {demoID: 'DEMO-M0017'})
SET d.dateOfBirth=date('1971-06-13'), d.age=54,
    d.administrativeGender='Female', d.sexAssignedAtBirth='Female',
    d.sexParamClinicalUse='Female-typical',
    d.zipCode='94110', d.state='CA', d.employmentStatus = 'Unemployed';
MERGE (e:Enrollment {enrollmentID: 'ENR-M0017'})
SET e.enrollmentStartDate=date('2026-01-01'), e.enrollmentEndDate=date('2026-12-31'),
    e.continuouslyEnrolled=true, e.measurementYear=2026,
    e.measureLookbackStart=date('2024-10-01'), e.measureLookbackEnd=date('2026-12-31'),
    e.proactiveLookbackStart=date('2025-06-01'), e.disenrolled=false, e.deceased=false;
MERGE (arc:AgeRuleCheck {ageRuleID: 'ARC-M0017'})
SET arc.eligibilityAgeCheck=true, arc.lookbackAgeCheck=true,
    arc.ageAtLastMammogram=54, arc.medicare66PlusInSNP_LTC=false;
MERGE (ep:ExclusionProfile {exclusionID: 'EXC-M0017'})
SET ep.bilateralMastectomy=false, ep.anyExclusionPresent=false;
MERGE (v:Vitals {vitalsID: 'VIT-M0017'}) SET v.status='UNASSIGNED';
MERGE (ch:ClinicalHistory {historyID: 'CLH-M0017'}) SET ch.status='UNASSIGNED';
MERGE (sh:ScreeningHistory {screeningID: 'SCR-M0017'})
SET sh.lastMammogramDate=date('2026-03-06'),
    sh.mammogramType='Screening', sh.icd10Code='Z00.00',
    sh.cptCode='77067', sh.claimID='C000034',
    sh.fallsInLookbackWindow=true,
    sh.hedisCompliant=true,
    sh.screeningStatus='COMPLIANT — Within lookback window',
    sh.inNetworkFacility=true;
MERGE (cg:CareGap {careGapID: 'GAP-BCS-M0017'})
SET cg.measureID='BCS', cg.gapStatus='CLOSED',
    cg.gapClosedDate=date('2026-03-06'),
    cg.reason='Mammogram 2026-03-06 — within lookback window — HEDIS compliant';
MERGE (sd:SDOH {sdohID: 'SDOH-M0017'}) SET sd.status='UNASSIGNED';
MERGE (con:Consent {consentID: 'CON-M0017'}) SET con.optOutOfOutreach=false;
MERGE (m:Member {memberID: 'M0017'})
MERGE (d:Demographics {demoID: 'DEMO-M0017'})
MERGE (e:Enrollment {enrollmentID: 'ENR-M0017'})
MERGE (arc:AgeRuleCheck {ageRuleID: 'ARC-M0017'})
MERGE (ep:ExclusionProfile {exclusionID: 'EXC-M0017'})
MERGE (v:Vitals {vitalsID: 'VIT-M0017'})
MERGE (ch:ClinicalHistory {historyID: 'CLH-M0017'})
MERGE (sh:ScreeningHistory {screeningID: 'SCR-M0017'})
MERGE (cg:CareGap {careGapID: 'GAP-BCS-M0017'})
MERGE (sd:SDOH {sdohID: 'SDOH-M0017'})
MERGE (con:Consent {consentID: 'CON-M0017'})
MERGE (bp:BenefitPlan {planID: 'PL-001'})
MERGE (pcp:Provider {providerID: 'P1012'})
MERGE (rad:Provider {providerID: 'P1017'})
MERGE (qm:QualityMeasure {measureID: 'BCS'})
MERGE (m)-[:HAS_DEMOGRAPHICS]->(d)
MERGE (m)-[:HAS_ENROLLMENT]->(e)
MERGE (m)-[:HAS_AGE_RULE_CHECK]->(arc)
MERGE (m)-[:HAS_EXCLUSION_PROFILE]->(ep)
MERGE (m)-[:HAS_VITALS]->(v)
MERGE (m)-[:HAS_CLINICAL_HISTORY]->(ch)
MERGE (m)-[:HAS_SCREENING_HISTORY]->(sh)
MERGE (m)-[:HAS_CARE_GAP]->(cg)
MERGE (m)-[:HAS_SDOH]->(sd)
MERGE (m)-[:HAS_CONSENT]->(con)
MERGE (m)-[:ENROLLED_IN]->(bp)
MERGE (m)-[:HAS_PCP]->(pcp)
MERGE (sh)-[:PERFORMED_BY]->(rad)
MERGE (cg)-[:TRACKED_UNDER]->(qm);

// M0018 — Emery Iyer | F | Age 24 | NOT ELIGIBLE (Age < 42)
MERGE (m:Member {memberID: 'M0018'}) SET m.fullName='Emery Iyer';
MERGE (d:Demographics {demoID: 'DEMO-M0018'})
SET d.dateOfBirth=date('2001-12-24'), d.age=24,
    d.administrativeGender='Female', d.zipCode='77002', d.state='TX';
MERGE (e:Enrollment {enrollmentID: 'ENR-M0018'})
SET e.enrollmentStartDate=date('2026-01-01'), e.enrollmentEndDate=date('2026-12-31'),
    e.continuouslyEnrolled=true, e.measurementYear=2026,
    e.measureLookbackStart=date('2024-10-01'), e.measureLookbackEnd=date('2026-12-31'),
    e.proactiveLookbackStart=date('2025-06-01'), e.disenrolled=false, e.deceased=false;
MERGE (arc:AgeRuleCheck {ageRuleID: 'ARC-M0018'})
SET arc.eligibilityAgeCheck=false, arc.medicare66PlusInSNP_LTC=false;
MERGE (cg:CareGap {careGapID: 'GAP-BCS-M0018'})
SET cg.measureID='BCS', cg.gapStatus='NOT ELIGIBLE', cg.reason='Age 24 — below 42 threshold';
MERGE (m:Member {memberID: 'M0018'})
MERGE (d:Demographics {demoID: 'DEMO-M0018'})
MERGE (e:Enrollment {enrollmentID: 'ENR-M0018'})
MERGE (arc:AgeRuleCheck {ageRuleID: 'ARC-M0018'})
MERGE (cg:CareGap {careGapID: 'GAP-BCS-M0018'})
MERGE (bp:BenefitPlan {planID: 'PL-001'})
MERGE (pcp:Provider {providerID: 'P1017'})
MERGE (m)-[:HAS_DEMOGRAPHICS]->(d)
MERGE (m)-[:HAS_ENROLLMENT]->(e)
MERGE (m)-[:HAS_AGE_RULE_CHECK]->(arc)
MERGE (m)-[:ENROLLED_IN]->(bp)
MERGE (m)-[:HAS_PCP]->(pcp)
MERGE (m)-[:HAS_CARE_GAP]->(cg);

// M0019 — Jamie Nguyen | F | Age 72 | BCS ELIGIBLE — No mammogram found
MERGE (m:Member {memberID: 'M0019'}) SET m.fullName='Jamie Nguyen';
MERGE (d:Demographics {demoID: 'DEMO-M0019'})
SET d.dateOfBirth=date('1953-12-02'), d.age=72,
    d.administrativeGender='Female', d.sexAssignedAtBirth='Female',
    d.zipCode='94110', d.state='CA', d.employmentStatus = 'Employed';
MERGE (e:Enrollment {enrollmentID: 'ENR-M0019'})
SET e.enrollmentStartDate=date('2026-01-01'), e.enrollmentEndDate=date('2026-12-31'),
    e.continuouslyEnrolled=true, e.measurementYear=2026,
    e.measureLookbackStart=date('2024-10-01'), e.measureLookbackEnd=date('2026-12-31'),
    e.proactiveLookbackStart=date('2025-06-01'), e.disenrolled=false, e.deceased=false;
MERGE (arc:AgeRuleCheck {ageRuleID: 'ARC-M0019'})
SET arc.eligibilityAgeCheck=true, arc.lookbackAgeCheck=true,
    arc.medicare66PlusInSNP_LTC=false;
MERGE (ep:ExclusionProfile {exclusionID: 'EXC-M0019'})
SET ep.bilateralMastectomy=false, ep.anyExclusionPresent=false;
MERGE (v:Vitals {vitalsID: 'VIT-M0019'}) SET v.status='UNASSIGNED';
MERGE (ch:ClinicalHistory {historyID: 'CLH-M0019'}) SET ch.status='UNASSIGNED';
MERGE (sh:ScreeningHistory {screeningID: 'SCR-M0019'})
SET sh.lastMammogramDate=null, sh.fallsInLookbackWindow=false,
    sh.screeningStatus='No mammogram claim found';
MERGE (cg:CareGap {careGapID: 'GAP-BCS-M0019'})
SET cg.measureID='BCS', cg.gapStatus='OPEN',
    cg.gapCreatedDate=date('2026-01-01'), cg.priorityLevel='PENDING',
    cg.reason='No BCS mammogram claim found';
MERGE (sd:SDOH {sdohID: 'SDOH-M0019'}) SET sd.status='UNASSIGNED';
MERGE (con:Consent {consentID: 'CON-M0019'}) SET con.optOutOfOutreach=false;
MERGE (m:Member {memberID: 'M0019'})
MERGE (d:Demographics {demoID: 'DEMO-M0019'})
MERGE (e:Enrollment {enrollmentID: 'ENR-M0019'})
MERGE (arc:AgeRuleCheck {ageRuleID: 'ARC-M0019'})
MERGE (ep:ExclusionProfile {exclusionID: 'EXC-M0019'})
MERGE (v:Vitals {vitalsID: 'VIT-M0019'})
MERGE (ch:ClinicalHistory {historyID: 'CLH-M0019'})
MERGE (sh:ScreeningHistory {screeningID: 'SCR-M0019'})
MERGE (cg:CareGap {careGapID: 'GAP-BCS-M0019'})
MERGE (sd:SDOH {sdohID: 'SDOH-M0019'})
MERGE (con:Consent {consentID: 'CON-M0019'})
MERGE (bp:BenefitPlan {planID: 'PL-001'})
MERGE (pcp:Provider {providerID: 'P1012'})
MERGE (qm:QualityMeasure {measureID: 'BCS'})
MERGE (m)-[:HAS_DEMOGRAPHICS]->(d)
MERGE (m)-[:HAS_ENROLLMENT]->(e)
MERGE (m)-[:HAS_AGE_RULE_CHECK]->(arc)
MERGE (m)-[:HAS_EXCLUSION_PROFILE]->(ep)
MERGE (m)-[:HAS_VITALS]->(v)
MERGE (m)-[:HAS_CLINICAL_HISTORY]->(ch)
MERGE (m)-[:HAS_SCREENING_HISTORY]->(sh)
MERGE (m)-[:HAS_CARE_GAP]->(cg)
MERGE (m)-[:HAS_SDOH]->(sd)
MERGE (m)-[:HAS_CONSENT]->(con)
MERGE (m)-[:ENROLLED_IN]->(bp)
MERGE (m)-[:HAS_PCP]->(pcp)
MERGE (cg)-[:TRACKED_UNDER]->(qm);

// M0020 — Logan Brooks | F | Age 29 | NOT ELIGIBLE (Age < 42)
// Has CPT 77067 claim but below eligibility age
MERGE (m:Member {memberID: 'M0020'}) SET m.fullName='Logan Brooks';
MERGE (d:Demographics {demoID: 'DEMO-M0020'})
SET d.dateOfBirth=date('1996-11-02'), d.age=29,
    d.administrativeGender='Female', d.zipCode='28202', d.state='NC';
MERGE (e:Enrollment {enrollmentID: 'ENR-M0020'})
SET e.enrollmentStartDate=date('2026-01-01'), e.enrollmentEndDate=date('2026-12-31'),
    e.continuouslyEnrolled=true, e.measurementYear=2026,
    e.measureLookbackStart=date('2024-10-01'), e.measureLookbackEnd=date('2026-12-31'),
    e.proactiveLookbackStart=date('2025-06-01'), e.disenrolled=false, e.deceased=false;
MERGE (arc:AgeRuleCheck {ageRuleID: 'ARC-M0020'})
SET arc.eligibilityAgeCheck=false, arc.medicare66PlusInSNP_LTC=false;
MERGE (cg:CareGap {careGapID: 'GAP-BCS-M0020'})
SET cg.measureID='BCS', cg.gapStatus='NOT ELIGIBLE',
    cg.reason='Age 29 — below 42 threshold';
MERGE (m:Member {memberID: 'M0020'})
MERGE (d:Demographics {demoID: 'DEMO-M0020'})
MERGE (e:Enrollment {enrollmentID: 'ENR-M0020'})
MERGE (arc:AgeRuleCheck {ageRuleID: 'ARC-M0020'})
MERGE (cg:CareGap {careGapID: 'GAP-BCS-M0020'})
MERGE (bp:BenefitPlan {planID: 'PL-001'})
MERGE (pcp:Provider {providerID: 'P1008'})
MERGE (m)-[:HAS_DEMOGRAPHICS]->(d)
MERGE (m)-[:HAS_ENROLLMENT]->(e)
MERGE (m)-[:HAS_AGE_RULE_CHECK]->(arc)
MERGE (m)-[:ENROLLED_IN]->(bp)
MERGE (m)-[:HAS_PCP]->(pcp)
MERGE (m)-[:HAS_CARE_GAP]->(cg);

// M0021 — Finley Gupta | F | Age 37 | NOT ELIGIBLE (Age < 42)
MERGE (m:Member {memberID: 'M0021'}) SET m.fullName='Finley Gupta';
MERGE (d:Demographics {demoID: 'DEMO-M0021'})
SET d.dateOfBirth=date('1988-08-01'), d.age=37,
    d.administrativeGender='Female', d.zipCode='77002', d.state='TX';
MERGE (e:Enrollment {enrollmentID: 'ENR-M0021'})
SET e.enrollmentStartDate=date('2026-01-01'), e.enrollmentEndDate=date('2026-12-31'),
    e.continuouslyEnrolled=true, e.measurementYear=2026,
    e.measureLookbackStart=date('2024-10-01'), e.measureLookbackEnd=date('2026-12-31'),
    e.proactiveLookbackStart=date('2025-06-01'), e.disenrolled=false, e.deceased=false;
MERGE (arc:AgeRuleCheck {ageRuleID: 'ARC-M0021'})
SET arc.eligibilityAgeCheck=false, arc.medicare66PlusInSNP_LTC=false;
MERGE (cg:CareGap {careGapID: 'GAP-BCS-M0021'})
SET cg.measureID='BCS', cg.gapStatus='NOT ELIGIBLE', cg.reason='Age 37 — below 42 threshold';
MERGE (m:Member {memberID: 'M0021'})
MERGE (d:Demographics {demoID: 'DEMO-M0021'})
MERGE (e:Enrollment {enrollmentID: 'ENR-M0021'})
MERGE (arc:AgeRuleCheck {ageRuleID: 'ARC-M0021'})
MERGE (cg:CareGap {careGapID: 'GAP-BCS-M0021'})
MERGE (bp:BenefitPlan {planID: 'PL-001'})
MERGE (pcp:Provider {providerID: 'P1000'})
MERGE (m)-[:HAS_DEMOGRAPHICS]->(d)
MERGE (m)-[:HAS_ENROLLMENT]->(e)
MERGE (m)-[:HAS_AGE_RULE_CHECK]->(arc)
MERGE (m)-[:ENROLLED_IN]->(bp)
MERGE (m)-[:HAS_PCP]->(pcp)
MERGE (m)-[:HAS_CARE_GAP]->(cg);

// M0022 — Morgan Gupta | M | Age 37 | NOT ELIGIBLE (Male)
MERGE (m:Member {memberID: 'M0022'}) SET m.fullName='Morgan Gupta';
MERGE (d:Demographics {demoID: 'DEMO-M0022'})
SET d.dateOfBirth=date('1988-05-02'), d.age=37,
    d.administrativeGender='Male', d.zipCode='02116', d.state='MA';
MERGE (e:Enrollment {enrollmentID: 'ENR-M0022'})
SET e.enrollmentStartDate=date('2026-01-01'), e.enrollmentEndDate=date('2026-12-31'),
    e.continuouslyEnrolled=true, e.measurementYear=2026,
    e.measureLookbackStart=date('2024-10-01'), e.measureLookbackEnd=date('2026-12-31'),
    e.proactiveLookbackStart=date('2025-06-01'), e.disenrolled=false, e.deceased=false;
MERGE (cg:CareGap {careGapID: 'GAP-BCS-M0022'})
SET cg.measureID='BCS', cg.gapStatus='NOT ELIGIBLE', cg.reason='Male';
MERGE (m:Member {memberID: 'M0022'})
MERGE (d:Demographics {demoID: 'DEMO-M0022'})
MERGE (e:Enrollment {enrollmentID: 'ENR-M0022'})
MERGE (cg:CareGap {careGapID: 'GAP-BCS-M0022'})
MERGE (bp:BenefitPlan {planID: 'PL-001'})
MERGE (pcp:Provider {providerID: 'P1007'})
MERGE (m)-[:HAS_DEMOGRAPHICS]->(d)
MERGE (m)-[:HAS_ENROLLMENT]->(e)
MERGE (m)-[:ENROLLED_IN]->(bp)
MERGE (m)-[:HAS_PCP]->(pcp)
MERGE (m)-[:HAS_CARE_GAP]->(cg);

// M0023 — Blair Gupta | M | Age 50 | NOT ELIGIBLE (Male)
MERGE (m:Member {memberID: 'M0023'}) SET m.fullName='Blair Gupta';
MERGE (d:Demographics {demoID: 'DEMO-M0023'})
SET d.dateOfBirth=date('1975-09-21'), d.age=50,
    d.administrativeGender='Male', d.zipCode='10016', d.state='NY';
MERGE (e:Enrollment {enrollmentID: 'ENR-M0023'})
SET e.enrollmentStartDate=date('2026-01-01'), e.enrollmentEndDate=date('2026-12-31'),
    e.continuouslyEnrolled=true, e.measurementYear=2026,
    e.measureLookbackStart=date('2024-10-01'), e.measureLookbackEnd=date('2026-12-31'),
    e.proactiveLookbackStart=date('2025-06-01'), e.disenrolled=false, e.deceased=false;
MERGE (cg:CareGap {careGapID: 'GAP-BCS-M0023'})
SET cg.measureID='BCS', cg.gapStatus='NOT ELIGIBLE', cg.reason='Male';
MERGE (m:Member {memberID: 'M0023'})
MERGE (d:Demographics {demoID: 'DEMO-M0023'})
MERGE (e:Enrollment {enrollmentID: 'ENR-M0023'})
MERGE (cg:CareGap {careGapID: 'GAP-BCS-M0023'})
MERGE (bp:BenefitPlan {planID: 'PL-001'})
MERGE (pcp:Provider {providerID: 'P1012'})
MERGE (m)-[:HAS_DEMOGRAPHICS]->(d)
MERGE (m)-[:HAS_ENROLLMENT]->(e)
MERGE (m)-[:ENROLLED_IN]->(bp)
MERGE (m)-[:HAS_PCP]->(pcp)
MERGE (m)-[:HAS_CARE_GAP]->(cg);

// M0024 — Peyton Desai | M | Age 59 | NOT ELIGIBLE (Male)
MERGE (m:Member {memberID: 'M0024'}) SET m.fullName='Peyton Desai';
MERGE (d:Demographics {demoID: 'DEMO-M0024'})
SET d.dateOfBirth=date('1966-04-08'), d.age=59,
    d.administrativeGender='Male', d.zipCode='85004', d.state='AZ';
MERGE (e:Enrollment {enrollmentID: 'ENR-M0024'})
SET e.enrollmentStartDate=date('2026-01-01'), e.enrollmentEndDate=date('2026-12-31'),
    e.continuouslyEnrolled=true, e.measurementYear=2026,
    e.measureLookbackStart=date('2024-10-01'), e.measureLookbackEnd=date('2026-12-31'),
    e.proactiveLookbackStart=date('2025-06-01'), e.disenrolled=false, e.deceased=false;
MERGE (cg:CareGap {careGapID: 'GAP-BCS-M0024'})
SET cg.measureID='BCS', cg.gapStatus='NOT ELIGIBLE', cg.reason='Male';
MERGE (m:Member {memberID: 'M0024'})
MERGE (d:Demographics {demoID: 'DEMO-M0024'})
MERGE (e:Enrollment {enrollmentID: 'ENR-M0024'})
MERGE (cg:CareGap {careGapID: 'GAP-BCS-M0024'})
MERGE (bp:BenefitPlan {planID: 'PL-001'})
MERGE (pcp:Provider {providerID: 'P1007'})
MERGE (m)-[:HAS_DEMOGRAPHICS]->(d)
MERGE (m)-[:HAS_ENROLLMENT]->(e)
MERGE (m)-[:ENROLLED_IN]->(bp)
MERGE (m)-[:HAS_PCP]->(pcp)
MERGE (m)-[:HAS_CARE_GAP]->(cg);

// M0025 — Riley Patel | F | Age 58 | BCS ELIGIBLE — TWO mammogram claims found
MERGE (m:Member {memberID: 'M0025'}) SET m.fullName='Riley Patel';
MERGE (d:Demographics {demoID: 'DEMO-M0025'})
SET d.dateOfBirth=date('1967-09-08'), d.age=58,
    d.administrativeGender='Female', d.sexAssignedAtBirth='Female',
    d.sexParamClinicalUse='Female-typical',
    d.zipCode='19103', d.state='PA', d.employmentStatus = 'Employed';
MERGE (e:Enrollment {enrollmentID: 'ENR-M0025'})
SET e.enrollmentStartDate=date('2026-01-01'), e.enrollmentEndDate=date('2026-12-31'),
    e.continuouslyEnrolled=true, e.measurementYear=2026,
    e.measureLookbackStart=date('2024-10-01'), e.measureLookbackEnd=date('2026-12-31'),
    e.proactiveLookbackStart=date('2025-06-01'), e.disenrolled=false, e.deceased=false;
MERGE (arc:AgeRuleCheck {ageRuleID: 'ARC-M0025'})
SET arc.eligibilityAgeCheck=true, arc.lookbackAgeCheck=true,
    arc.ageAtLastMammogram=58, arc.medicare66PlusInSNP_LTC=false;
MERGE (ep:ExclusionProfile {exclusionID: 'EXC-M0025'})
SET ep.bilateralMastectomy=false, ep.anyExclusionPresent=false;
MERGE (v:Vitals {vitalsID: 'VIT-M0025'}) SET v.status='UNASSIGNED';
MERGE (ch:ClinicalHistory {historyID: 'CLH-M0025'}) SET ch.status='UNASSIGNED';
// Most recent mammogram: 2026-04-03 (C000051)
MERGE (sh:ScreeningHistory {screeningID: 'SCR-M0025'})
SET sh.lastMammogramDate=date('2026-04-03'),
    sh.mammogramType='Screening', sh.icd10Code='I10',
    sh.cptCode='77067', sh.claimID='C000051',
    sh.fallsInLookbackWindow=true, sh.hedisCompliant=true,
    sh.screeningStatus='COMPLIANT',
    sh.note='Two mammogram claims — C000050 (2026-01-18) and C000051 (2026-04-03)';
MERGE (cg:CareGap {careGapID: 'GAP-BCS-M0025'})
SET cg.measureID='BCS', cg.gapStatus='CLOSED',
    cg.gapClosedDate=date('2026-01-18'),
    cg.reason='Mammogram 2026-01-18 within window — HEDIS compliant';
MERGE (sd:SDOH {sdohID: 'SDOH-M0025'}) SET sd.status='UNASSIGNED';
MERGE (con:Consent {consentID: 'CON-M0025'}) SET con.optOutOfOutreach=false;
MERGE (m:Member {memberID: 'M0025'})
MERGE (d:Demographics {demoID: 'DEMO-M0025'})
MERGE (e:Enrollment {enrollmentID: 'ENR-M0025'})
MERGE (arc:AgeRuleCheck {ageRuleID: 'ARC-M0025'})
MERGE (ep:ExclusionProfile {exclusionID: 'EXC-M0025'})
MERGE (v:Vitals {vitalsID: 'VIT-M0025'})
MERGE (ch:ClinicalHistory {historyID: 'CLH-M0025'})
MERGE (sh:ScreeningHistory {screeningID: 'SCR-M0025'})
MERGE (cg:CareGap {careGapID: 'GAP-BCS-M0025'})
MERGE (sd:SDOH {sdohID: 'SDOH-M0025'})
MERGE (con:Consent {consentID: 'CON-M0025'})
MERGE (bp:BenefitPlan {planID: 'PL-001'})
MERGE (pcp:Provider {providerID: 'P1008'})
MERGE (qm:QualityMeasure {measureID: 'BCS'})
MERGE (m)-[:HAS_DEMOGRAPHICS]->(d)
MERGE (m)-[:HAS_ENROLLMENT]->(e)
MERGE (m)-[:HAS_AGE_RULE_CHECK]->(arc)
MERGE (m)-[:HAS_EXCLUSION_PROFILE]->(ep)
MERGE (m)-[:HAS_VITALS]->(v)
MERGE (m)-[:HAS_CLINICAL_HISTORY]->(ch)
MERGE (m)-[:HAS_SCREENING_HISTORY]->(sh)
MERGE (m)-[:HAS_CARE_GAP]->(cg)
MERGE (m)-[:HAS_SDOH]->(sd)
MERGE (m)-[:HAS_CONSENT]->(con)
MERGE (m)-[:ENROLLED_IN]->(bp)
MERGE (m)-[:HAS_PCP]->(pcp)
MERGE (cg)-[:TRACKED_UNDER]->(qm);

// M0026 — Dakota Alvarez | F | Age 75 | NOT ELIGIBLE (Age > 74)
// Has CPT 77067 claim but above eligibility age
MERGE (m:Member {memberID: 'M0026'}) SET m.fullName='Dakota Alvarez';
MERGE (d:Demographics {demoID: 'DEMO-M0026'})
SET d.dateOfBirth=date('1950-05-21'), d.age=75,
    d.administrativeGender='Female', d.sexAssignedAtBirth='Female',
    d.zipCode='07030', d.state='NJ', d.employmentStatus = 'Unemployed';
MERGE (e:Enrollment {enrollmentID: 'ENR-M0026'})
SET e.enrollmentStartDate=date('2026-01-01'), e.enrollmentEndDate=date('2026-12-31'),
    e.continuouslyEnrolled=true, e.measurementYear=2026,
    e.measureLookbackStart=date('2024-10-01'), e.measureLookbackEnd=date('2026-12-31'),
    e.proactiveLookbackStart=date('2025-06-01'), e.disenrolled=false, e.deceased=false;
MERGE (arc:AgeRuleCheck {ageRuleID: 'ARC-M0026'})
SET arc.eligibilityAgeCheck=false, // Age 75 — above 74 threshold
    arc.lookbackAgeCheck=false, arc.medicare66PlusInSNP_LTC=false;
MERGE (cg:CareGap {careGapID: 'GAP-BCS-M0026'})
SET cg.measureID='BCS', cg.gapStatus='NOT ELIGIBLE',
    cg.reason='Age 75 — above BCS eligibility threshold of 74';
MERGE (m:Member {memberID: 'M0026'})
MERGE (d:Demographics {demoID: 'DEMO-M0026'})
MERGE (e:Enrollment {enrollmentID: 'ENR-M0026'})
MERGE (arc:AgeRuleCheck {ageRuleID: 'ARC-M0026'})
MERGE (cg:CareGap {careGapID: 'GAP-BCS-M0026'})
MERGE (bp:BenefitPlan {planID: 'PL-001'})
MERGE (pcp:Provider {providerID: 'P1003'})
MERGE (m)-[:HAS_DEMOGRAPHICS]->(d)
MERGE (m)-[:HAS_ENROLLMENT]->(e)
MERGE (m)-[:HAS_AGE_RULE_CHECK]->(arc)
MERGE (m)-[:ENROLLED_IN]->(bp)
MERGE (m)-[:HAS_PCP]->(pcp)
MERGE (m)-[:HAS_CARE_GAP]->(cg);

// M0027 — Jordan Collins | F | Age 61 | BCS ELIGIBLE — No mammogram found
MERGE (m:Member {memberID: 'M0027'}) SET m.fullName='Jordan Collins';
MERGE (d:Demographics {demoID: 'DEMO-M0027'})
SET d.dateOfBirth=date('1964-08-02'), d.age=61,
    d.administrativeGender='Female', d.sexAssignedAtBirth='Female',
    d.zipCode='77002', d.state='TX', d.employmentStatus = 'Unemployed';
MERGE (e:Enrollment {enrollmentID: 'ENR-M0027'})
SET e.enrollmentStartDate=date('2026-01-01'), e.enrollmentEndDate=date('2026-12-31'),
    e.continuouslyEnrolled=true, e.measurementYear=2026,
    e.measureLookbackStart=date('2024-10-01'), e.measureLookbackEnd=date('2026-12-31'),
    e.proactiveLookbackStart=date('2025-06-01'), e.disenrolled=false, e.deceased=false;
MERGE (arc:AgeRuleCheck {ageRuleID: 'ARC-M0027'})
SET arc.eligibilityAgeCheck=true, arc.lookbackAgeCheck=true,
    arc.medicare66PlusInSNP_LTC=false;
MERGE (ep:ExclusionProfile {exclusionID: 'EXC-M0027'})
SET ep.bilateralMastectomy=false, ep.anyExclusionPresent=false;
MERGE (v:Vitals {vitalsID: 'VIT-M0027'}) SET v.status='UNASSIGNED';
MERGE (ch:ClinicalHistory {historyID: 'CLH-M0027'}) SET ch.status='UNASSIGNED';
MERGE (sh:ScreeningHistory {screeningID: 'SCR-M0027'})
SET sh.lastMammogramDate=null, sh.fallsInLookbackWindow=false,
    sh.screeningStatus='No mammogram claim found';
MERGE (cg:CareGap {careGapID: 'GAP-BCS-M0027'})
SET cg.measureID='BCS', cg.gapStatus='OPEN',
    cg.gapCreatedDate=date('2026-01-01'), cg.priorityLevel='PENDING',
    cg.reason='No BCS mammogram claim found';
MERGE (sd:SDOH {sdohID: 'SDOH-M0027'}) SET sd.status='UNASSIGNED';
MERGE (con:Consent {consentID: 'CON-M0027'}) SET con.optOutOfOutreach=false;
MERGE (m:Member {memberID: 'M0027'})
MERGE (d:Demographics {demoID: 'DEMO-M0027'})
MERGE (e:Enrollment {enrollmentID: 'ENR-M0027'})
MERGE (arc:AgeRuleCheck {ageRuleID: 'ARC-M0027'})
MERGE (ep:ExclusionProfile {exclusionID: 'EXC-M0027'})
MERGE (v:Vitals {vitalsID: 'VIT-M0027'})
MERGE (ch:ClinicalHistory {historyID: 'CLH-M0027'})
MERGE (sh:ScreeningHistory {screeningID: 'SCR-M0027'})
MERGE (cg:CareGap {careGapID: 'GAP-BCS-M0027'})
MERGE (sd:SDOH {sdohID: 'SDOH-M0027'})
MERGE (con:Consent {consentID: 'CON-M0027'})
MERGE (bp:BenefitPlan {planID: 'PL-001'})
MERGE (pcp:Provider {providerID: 'P1011'})
MERGE (qm:QualityMeasure {measureID: 'BCS'})
MERGE (m)-[:HAS_DEMOGRAPHICS]->(d)
MERGE (m)-[:HAS_ENROLLMENT]->(e)
MERGE (m)-[:HAS_AGE_RULE_CHECK]->(arc)
MERGE (m)-[:HAS_EXCLUSION_PROFILE]->(ep)
MERGE (m)-[:HAS_VITALS]->(v)
MERGE (m)-[:HAS_CLINICAL_HISTORY]->(ch)
MERGE (m)-[:HAS_SCREENING_HISTORY]->(sh)
MERGE (m)-[:HAS_CARE_GAP]->(cg)
MERGE (m)-[:HAS_SDOH]->(sd)
MERGE (m)-[:HAS_CONSENT]->(con)
MERGE (m)-[:ENROLLED_IN]->(bp)
MERGE (m)-[:HAS_PCP]->(pcp)
MERGE (cg)-[:TRACKED_UNDER]->(qm);

// M0028 — Morgan Kim | F | Age 73 | BCS ELIGIBLE — No mammogram found
MERGE (m:Member {memberID: 'M0028'}) SET m.fullName='Morgan Kim';
MERGE (d:Demographics {demoID: 'DEMO-M0028'})
SET d.dateOfBirth=date('1952-08-07'), d.age=73,
    d.administrativeGender='Female', d.sexAssignedAtBirth='Female',
    d.zipCode='28202', d.state='NC', d.employmentStatus = 'Self-employed';
MERGE (e:Enrollment {enrollmentID: 'ENR-M0028'})
SET e.enrollmentStartDate=date('2026-01-01'), e.enrollmentEndDate=date('2026-12-31'),
    e.continuouslyEnrolled=true, e.measurementYear=2026,
    e.measureLookbackStart=date('2024-10-01'), e.measureLookbackEnd=date('2026-12-31'),
    e.proactiveLookbackStart=date('2025-06-01'), e.disenrolled=false, e.deceased=false;
MERGE (arc:AgeRuleCheck {ageRuleID: 'ARC-M0028'})
SET arc.eligibilityAgeCheck=true, arc.lookbackAgeCheck=true,
    arc.medicare66PlusInSNP_LTC=false;
MERGE (ep:ExclusionProfile {exclusionID: 'EXC-M0028'})
SET ep.bilateralMastectomy=false, ep.anyExclusionPresent=false;
MERGE (v:Vitals {vitalsID: 'VIT-M0028'}) SET v.status='UNASSIGNED';
MERGE (ch:ClinicalHistory {historyID: 'CLH-M0028'}) SET ch.status='UNASSIGNED';
MERGE (sh:ScreeningHistory {screeningID: 'SCR-M0028'})
SET sh.lastMammogramDate=null, sh.fallsInLookbackWindow=false,
    sh.screeningStatus='No mammogram claim found';
MERGE (cg:CareGap {careGapID: 'GAP-BCS-M0028'})
SET cg.measureID='BCS', cg.gapStatus='OPEN',
    cg.gapCreatedDate=date('2026-01-01'), cg.priorityLevel='PENDING',
    cg.reason='No BCS mammogram claim found';
MERGE (sd:SDOH {sdohID: 'SDOH-M0028'}) SET sd.status='UNASSIGNED';
MERGE (con:Consent {consentID: 'CON-M0028'}) SET con.optOutOfOutreach=false;
MERGE (m:Member {memberID: 'M0028'})
MERGE (d:Demographics {demoID: 'DEMO-M0028'})
MERGE (e:Enrollment {enrollmentID: 'ENR-M0028'})
MERGE (arc:AgeRuleCheck {ageRuleID: 'ARC-M0028'})
MERGE (ep:ExclusionProfile {exclusionID: 'EXC-M0028'})
MERGE (v:Vitals {vitalsID: 'VIT-M0028'})
MERGE (ch:ClinicalHistory {historyID: 'CLH-M0028'})
MERGE (sh:ScreeningHistory {screeningID: 'SCR-M0028'})
MERGE (cg:CareGap {careGapID: 'GAP-BCS-M0028'})
MERGE (sd:SDOH {sdohID: 'SDOH-M0028'})
MERGE (con:Consent {consentID: 'CON-M0028'})
MERGE (bp:BenefitPlan {planID: 'PL-001'})
MERGE (pcp:Provider {providerID: 'P1004'})
MERGE (qm:QualityMeasure {measureID: 'BCS'})
MERGE (m)-[:HAS_DEMOGRAPHICS]->(d)
MERGE (m)-[:HAS_ENROLLMENT]->(e)
MERGE (m)-[:HAS_AGE_RULE_CHECK]->(arc)
MERGE (m)-[:HAS_EXCLUSION_PROFILE]->(ep)
MERGE (m)-[:HAS_VITALS]->(v)
MERGE (m)-[:HAS_CLINICAL_HISTORY]->(ch)
MERGE (m)-[:HAS_SCREENING_HISTORY]->(sh)
MERGE (m)-[:HAS_CARE_GAP]->(cg)
MERGE (m)-[:HAS_SDOH]->(sd)
MERGE (m)-[:HAS_CONSENT]->(con)
MERGE (m)-[:ENROLLED_IN]->(bp)
MERGE (m)-[:HAS_PCP]->(pcp)
MERGE (cg)-[:TRACKED_UNDER]->(qm);

// M0029 — Dakota Rao | F | Age 49 | NOT ELIGIBLE (Age < 50... wait — BCS-E starts at 42)
// Age 49 — ELIGIBLE under Hopkins BCS-E (42-74)
MERGE (m:Member {memberID: 'M0029'}) SET m.fullName='Dakota Rao';
MERGE (d:Demographics {demoID: 'DEMO-M0029'})
SET d.dateOfBirth=date('1976-07-27'), d.age=49,
    d.administrativeGender='Female', d.sexAssignedAtBirth='Female',
    d.sexParamClinicalUse='Female-typical',
    d.zipCode='33130', d.state='FL', d.employmentStatus = 'Employed';
MERGE (e:Enrollment {enrollmentID: 'ENR-M0029'})
SET e.enrollmentStartDate=date('2026-01-01'), e.enrollmentEndDate=date('2026-12-31'),
    e.continuouslyEnrolled=true, e.measurementYear=2026,
    e.measureLookbackStart=date('2024-10-01'), e.measureLookbackEnd=date('2026-12-31'),
    e.proactiveLookbackStart=date('2025-06-01'), e.disenrolled=false, e.deceased=false;
MERGE (arc:AgeRuleCheck {ageRuleID: 'ARC-M0029'})
SET arc.eligibilityAgeCheck=true,  // Age 49 — within 42-74 (Hopkins BCS-E)
    arc.lookbackAgeCheck=true, arc.ageAtLastMammogram=49,
    arc.medicare66PlusInSNP_LTC=false;
MERGE (ep:ExclusionProfile {exclusionID: 'EXC-M0029'})
SET ep.bilateralMastectomy=false, ep.anyExclusionPresent=false;
MERGE (v:Vitals {vitalsID: 'VIT-M0029'}) SET v.status='UNASSIGNED';
MERGE (ch:ClinicalHistory {historyID: 'CLH-M0029'}) SET ch.status='UNASSIGNED';
// Mammogram found: C000060 — CPT 77067, Z00.00, 2026-02-18
MERGE (sh:ScreeningHistory {screeningID: 'SCR-M0029'})
SET sh.lastMammogramDate=date('2026-02-18'),
    sh.mammogramType='Screening', sh.icd10Code='Z00.00',
    sh.cptCode='77067', sh.claimID='C000060',
    sh.fallsInLookbackWindow=true, sh.hedisCompliant=true,
    sh.screeningStatus='COMPLIANT — Within lookback window',
    sh.inNetworkFacility=true;
MERGE (cg:CareGap {careGapID: 'GAP-BCS-M0029'})
SET cg.measureID='BCS', cg.gapStatus='CLOSED',
    cg.gapClosedDate=date('2026-02-18'),
    cg.reason='Mammogram 2026-02-18 — within window — HEDIS compliant';
MERGE (sd:SDOH {sdohID: 'SDOH-M0029'}) SET sd.status='UNASSIGNED';
MERGE (con:Consent {consentID: 'CON-M0029'}) SET con.optOutOfOutreach=false;
MERGE (m:Member {memberID: 'M0029'})
MERGE (d:Demographics {demoID: 'DEMO-M0029'})
MERGE (e:Enrollment {enrollmentID: 'ENR-M0029'})
MERGE (arc:AgeRuleCheck {ageRuleID: 'ARC-M0029'})
MERGE (ep:ExclusionProfile {exclusionID: 'EXC-M0029'})
MERGE (v:Vitals {vitalsID: 'VIT-M0029'})
MERGE (ch:ClinicalHistory {historyID: 'CLH-M0029'})
MERGE (sh:ScreeningHistory {screeningID: 'SCR-M0029'})
MERGE (cg:CareGap {careGapID: 'GAP-BCS-M0029'})
MERGE (sd:SDOH {sdohID: 'SDOH-M0029'})
MERGE (con:Consent {consentID: 'CON-M0029'})
MERGE (bp:BenefitPlan {planID: 'PL-001'})
MERGE (pcp:Provider {providerID: 'P1016'})
MERGE (qm:QualityMeasure {measureID: 'BCS'})
MERGE (m)-[:HAS_DEMOGRAPHICS]->(d)
MERGE (m)-[:HAS_ENROLLMENT]->(e)
MERGE (m)-[:HAS_AGE_RULE_CHECK]->(arc)
MERGE (m)-[:HAS_EXCLUSION_PROFILE]->(ep)
MERGE (m)-[:HAS_VITALS]->(v)
MERGE (m)-[:HAS_CLINICAL_HISTORY]->(ch)
MERGE (m)-[:HAS_SCREENING_HISTORY]->(sh)
MERGE (m)-[:HAS_CARE_GAP]->(cg)
MERGE (m)-[:HAS_SDOH]->(sd)
MERGE (m)-[:HAS_CONSENT]->(con)
MERGE (m)-[:ENROLLED_IN]->(bp)
MERGE (m)-[:HAS_PCP]->(pcp)
MERGE (cg)-[:TRACKED_UNDER]->(qm);

// M0030 — Finley Patel | M | Age 72 | NOT ELIGIBLE (Male)
MERGE (m:Member {memberID: 'M0030'}) SET m.fullName='Finley Patel';
MERGE (d:Demographics {demoID: 'DEMO-M0030'})
SET d.dateOfBirth=date('1953-04-22'), d.age=72,
    d.administrativeGender='Male', d.zipCode='43215', d.state='OH';
MERGE (e:Enrollment {enrollmentID: 'ENR-M0030'})
SET e.enrollmentStartDate=date('2026-01-01'), e.enrollmentEndDate=date('2026-12-31'),
    e.continuouslyEnrolled=true, e.measurementYear=2026,
    e.measureLookbackStart=date('2024-10-01'), e.measureLookbackEnd=date('2026-12-31'),
    e.proactiveLookbackStart=date('2025-06-01'), e.disenrolled=false, e.deceased=false;
MERGE (cg:CareGap {careGapID: 'GAP-BCS-M0030'})
SET cg.measureID='BCS', cg.gapStatus='NOT ELIGIBLE', cg.reason='Male';
MERGE (m:Member {memberID: 'M0030'})
MERGE (d:Demographics {demoID: 'DEMO-M0030'})
MERGE (e:Enrollment {enrollmentID: 'ENR-M0030'})
MERGE (cg:CareGap {careGapID: 'GAP-BCS-M0030'})
MERGE (bp:BenefitPlan {planID: 'PL-001'})
MERGE (pcp:Provider {providerID: 'P1017'})
MERGE (m)-[:HAS_DEMOGRAPHICS]->(d)
MERGE (m)-[:HAS_ENROLLMENT]->(e)
MERGE (m)-[:ENROLLED_IN]->(bp)
MERGE (m)-[:HAS_PCP]->(pcp)
MERGE (m)-[:HAS_CARE_GAP]->(cg);


// ============================================================
// SECTION 3: BCS-RELEVANT CLAIMS ONLY
// Only mammogram CPT codes: 77067, 77066, 77065, 77062, 77061, 77063
// ============================================================

// C000012 — M0006 — CPT 77067 (Male — not BCS eligible but claim exists)
MERGE (c:Claim {claimID: 'C000012'})
SET c.memberID='M0006', c.providerID='P1016', c.cptCode='77067',
    c.icd10Code='I10', c.serviceDate=date('2026-02-16'),
    c.claimStatus='Paid', c.claimType='Screening',
    c.hedisCompliant=false, c.note='Member is Male — not BCS eligible';
MERGE (m:Member {memberID: 'M0006'})
MERGE (p:Provider {providerID: 'P1016'})
MERGE (m)-[:HAS_CLAIM]->(c)
MERGE (c)-[:BILLED_BY]->(p);

// C000027 — M0013 — CPT 77067 (Male — not BCS eligible)
MERGE (c:Claim {claimID: 'C000027'})
SET c.memberID='M0013', c.providerID='P1003', c.cptCode='77067',
    c.icd10Code='I10', c.serviceDate=date('2026-03-27'),
    c.claimStatus='Paid', c.claimType='Screening',
    c.hedisCompliant=false, c.note='Member is Male — not BCS eligible';
MERGE (m:Member {memberID: 'M0013'})
MERGE (p:Provider {providerID: 'P1003'})
MERGE (m)-[:HAS_CLAIM]->(c)
MERGE (c)-[:BILLED_BY]->(p);

// C000034 — M0017 — CPT 77067 (Female 54 — COMPLIANT)
MERGE (c:Claim {claimID: 'C000034'})
SET c.memberID='M0017', c.providerID='P1017', c.cptCode='77067',
    c.icd10Code='Z00.00', c.serviceDate=date('2026-03-06'),
    c.claimStatus='Paid', c.claimType='Screening',
    c.hedisCompliant=true,
    c.fallsInLookbackWindow=true,
    c.note='Valid BCS screening claim — closes gap';
MERGE (m:Member {memberID: 'M0017'})
MERGE (p:Provider {providerID: 'P1017'})
MERGE (sh:ScreeningHistory {screeningID: 'SCR-M0017'})
MERGE (m)-[:HAS_CLAIM]->(c)
MERGE (c)-[:BILLED_BY]->(p)
MERGE (sh)-[:DOCUMENTED_IN]->(c);

// C000036 — M0018 — CPT 77067 (Female 24 — not eligible by age)
MERGE (c:Claim {claimID: 'C000036'})
SET c.memberID='M0018', c.providerID='P1012', c.cptCode='77067',
    c.icd10Code='J06.9', c.serviceDate=date('2026-01-10'),
    c.claimStatus='Paid', c.claimType='Screening',
    c.hedisCompliant=false, c.note='Member age 24 — below 42 eligibility threshold';
MERGE (m:Member {memberID: 'M0018'})
MERGE (p:Provider {providerID: 'P1012'})
MERGE (m)-[:HAS_CLAIM]->(c)
MERGE (c)-[:BILLED_BY]->(p);

// C000039 — M0020 — CPT 77067 (Female 29 — not eligible by age)
MERGE (c:Claim {claimID: 'C000039'})
SET c.memberID='M0020', c.providerID='P1012', c.cptCode='77067',
    c.icd10Code='J06.9', c.serviceDate=date('2026-02-07'),
    c.claimStatus='Paid', c.claimType='Screening',
    c.hedisCompliant=false, c.note='Member age 29 — below 42 eligibility threshold';
MERGE (m:Member {memberID: 'M0020'})
MERGE (p:Provider {providerID: 'P1012'})
MERGE (m)-[:HAS_CLAIM]->(c)
MERGE (c)-[:BILLED_BY]->(p);

// C000050 — M0025 — CPT 77067 First mammogram (COMPLIANT)
MERGE (c:Claim {claimID: 'C000050'})
SET c.memberID='M0025', c.providerID='P1009', c.cptCode='77067',
    c.icd10Code='I10', c.serviceDate=date('2026-01-18'),
    c.claimStatus='Paid', c.claimType='Screening',
    c.hedisCompliant=true, c.fallsInLookbackWindow=true,
    c.note='First BCS claim — within window';
MERGE (m:Member {memberID: 'M0025'})
MERGE (p:Provider {providerID: 'P1009'})
MERGE (m)-[:HAS_CLAIM]->(c)
MERGE (c)-[:BILLED_BY]->(p);

// C000051 — M0025 — CPT 77067 Second mammogram (COMPLIANT)
MERGE (c:Claim {claimID: 'C000051'})
SET c.memberID='M0025', c.providerID='P1001', c.cptCode='77067',
    c.icd10Code='I10', c.serviceDate=date('2026-04-03'),
    c.claimStatus='Paid', c.claimType='Screening',
    c.hedisCompliant=true, c.fallsInLookbackWindow=true,
    c.note='Second BCS claim — within window';
MERGE (m:Member {memberID: 'M0025'})
MERGE (p:Provider {providerID: 'P1001'})
MERGE (sh:ScreeningHistory {screeningID: 'SCR-M0025'})
MERGE (m)-[:HAS_CLAIM]->(c)
MERGE (c)-[:BILLED_BY]->(p)
MERGE (sh)-[:DOCUMENTED_IN]->(c);

// C000053 — M0026 — CPT 77067 (Female 75 — above eligibility age)
MERGE (c:Claim {claimID: 'C000053'})
SET c.memberID='M0026', c.providerID='P1003', c.cptCode='77067',
    c.icd10Code='J06.9', c.serviceDate=date('2026-03-17'),
    c.claimStatus='Paid', c.claimType='Screening',
    c.hedisCompliant=false, c.note='Member age 75 — above 74 BCS eligibility';
MERGE (m:Member {memberID: 'M0026'})
MERGE (p:Provider {providerID: 'P1003'})
MERGE (m)-[:HAS_CLAIM]->(c)
MERGE (c)-[:BILLED_BY]->(p);

// C000060 — M0029 — CPT 77067 (Female 49 — COMPLIANT under Hopkins BCS-E)
MERGE (c:Claim {claimID: 'C000060'})
SET c.memberID='M0029', c.providerID='P1000', c.cptCode='77067',
    c.icd10Code='Z00.00', c.serviceDate=date('2026-02-18'),
    c.claimStatus='Paid', c.claimType='Screening',
    c.hedisCompliant=true, c.fallsInLookbackWindow=true,
    c.note='Valid BCS screening — Hopkins BCS-E age 42-74 — age 49 eligible';
MERGE (m:Member {memberID: 'M0029'})
MERGE (p:Provider {providerID: 'P1000'})
MERGE (sh:ScreeningHistory {screeningID: 'SCR-M0029'})
MERGE (m)-[:HAS_CLAIM]->(c)
MERGE (c)-[:BILLED_BY]->(p)
MERGE (sh)-[:DOCUMENTED_IN]->(c);

// C000073 — M0011 — CPT 77067 OUTSIDE WINDOW (KEY CLAIM)
MERGE (c:Claim {claimID: 'C000073'})
SET c.memberID='M0011', c.providerID='P1016', c.cptCode='77067',
    c.icd10Code='Z12.31', c.serviceDate=date('2023-10-04'),
    c.claimStatus='Paid', c.claimType='Screening',
    c.hedisCompliant=false,
    c.fallsInLookbackWindow=false,
    c.windowNote='2023-10-04 is BEFORE window start 2024-10-01',
    c.ageAtService=39,
    c.ageRuleNote='Member was 39 at service — below 40 lookback age threshold',
    c.monthsSinceService=29;
MERGE (m:Member {memberID: 'M0011'})
MERGE (p:Provider {providerID: 'P1016'})
MERGE (sh:ScreeningHistory {screeningID: 'SCR-M0011'})
MERGE (m)-[:HAS_CLAIM]->(c)
MERGE (c)-[:BILLED_BY]->(p)
MERGE (sh)-[:DOCUMENTED_IN]->(c);


// ============================================================
// SECTION 4: OUTREACH RECORDS (from CareMngnt_Outreach_Dashboard)
// BCS outreach only
// ============================================================

// Outreach for M0011 — GAP-BCS-M0011
MERGE (o:Outreach {outreachID: 'OUT-BCS-1'})
SET o.careGapID       = 'GAP-BCS-M0011',
    o.memberID        = 'M0011',
    o.careManagerID   = 'CM-101',
    o.channel         = 'Phone',
    o.outreachDate    = date('2026-02-12'),
    o.outreachStatus  = 'Attempted',
    o.outcome         = 'No Answer',
    o.followupDate    = date('2026-02-26');

MERGE (cg:CareGap {careGapID: 'GAP-BCS-M0011'})
MERGE (m:Member {memberID: 'M0011'})
MERGE (cg)-[:TRIGGERED_OUTREACH]->(o)
MERGE (m)-[:HAS_OUTREACH]->(o);

// Care Manager
MERGE (cm:CareManager {careManagerID: 'CM-101'})
SET cm.careManagerName='Care Manager 101',
    cm.specialty='BCS', cm.status='Active';
MERGE (o:Outreach {outreachID: 'OUT-BCS-1'})
MERGE (cm:CareManager {careManagerID: 'CM-101'})
MERGE (o)-[:PERFORMED_BY]->(cm);


// ============================================================
// SECTION 5: VERIFICATION QUERIES
// Run these after loading to confirm data is correct
// ============================================================

// Q1: Count all members loaded
// MATCH (m:Member) RETURN count(m) AS totalMembers;
// Expected: 30

// Q2: BCS eligible female members (42-74)
// MATCH (m:Member)-[:HAS_DEMOGRAPHICS]->(d:Demographics)
// MATCH (m)-[:HAS_AGE_RULE_CHECK]->(arc:AgeRuleCheck)
// WHERE d.administrativeGender = 'Female'
//   AND arc.eligibilityAgeCheck = true
// RETURN m.memberID, m.fullName, d.age, d.state
// ORDER BY d.age;

// Q3: BCS Care Gap Status Summary
// MATCH (m:Member)-[:HAS_CARE_GAP]->(cg:CareGap {measureID: 'BCS'})
// RETURN cg.gapStatus AS Status, count(m) AS MemberCount
// ORDER BY MemberCount DESC;

// Q4: All open BCS gaps
// MATCH (m:Member)-[:HAS_CARE_GAP]->(cg:CareGap {measureID: 'BCS', gapStatus: 'OPEN'})
// MATCH (m)-[:HAS_DEMOGRAPHICS]->(d:Demographics)
// RETURN m.memberID, m.fullName, d.age, cg.reason
// ORDER BY d.age DESC;

// Q5: Mammogram claims within lookback window
// MATCH (m:Member)-[:HAS_CLAIM]->(c:Claim)
// WHERE c.cptCode IN ['77067','77066','77065','77062','77061','77063']
//   AND c.hedisCompliant = true
// RETURN m.memberID, c.claimID, c.cptCode, c.serviceDate, c.hedisCompliant;

// Q6: Screening history compliance check
// MATCH (m:Member)-[:HAS_SCREENING_HISTORY]->(sh:ScreeningHistory)
// MATCH (m)-[:HAS_DEMOGRAPHICS]->(d:Demographics)
// WHERE d.administrativeGender = 'Female'
// RETURN m.memberID, m.fullName, d.age,
//        sh.lastMammogramDate, sh.fallsInLookbackWindow,
//        sh.screeningStatus
// ORDER BY sh.fallsInLookbackWindow DESC;

// Q7: Members pending clinical data enrichment
// MATCH (m:Member)-[:HAS_CLINICAL_HISTORY]->(ch:ClinicalHistory {status: 'PENDING'})
// MATCH (m)-[:HAS_CARE_GAP]->(cg:CareGap {measureID: 'BCS', gapStatus: 'OPEN'})
// RETURN m.memberID, m.fullName, cg.gapStatus, cg.reason;

// Q8: Outreach tracking
// MATCH (m:Member)-[:HAS_OUTREACH]->(o:Outreach)
// MATCH (m)-[:HAS_CARE_GAP]->(cg:CareGap)
// RETURN m.memberID, m.fullName, o.channel, o.outreachDate,
//        o.outreachStatus, o.outcome, cg.gapStatus;


// ============================================================
// SECTION 6: DATA STATUS SUMMARY
// What's loaded vs what's pending
// ============================================================

// LOADED FROM EXCEL:
//   Member (30) ✅
//   Demographics (30) ✅
//   Enrollment (30) ✅
//   BenefitPlan (1 — PL-001) ✅
//   Provider (18 — P1000-P1017) ✅
//   QualityMeasure (1 — BCS) ✅
//   AgeRuleCheck (female/eligible members) ✅
//   ExclusionProfile (female/eligible members) ✅
//   ScreeningHistory (from BCS claims) ✅
//   Claim (BCS mammogram claims only) ✅
//   CareGap (all 30 members) ✅
//   Outreach (BCS outreach only) ✅
//   CareManager (CM-101) ✅

// PENDING — Need EHR / Clinical Data Source:
//   Vitals (BP, BMI, Height, Weight)
//   ClinicalHistory (family history, BRCA, dense breast, biopsy)
//   Medication (HRT, comorbidity meds)
//   ReproductiveHistory (menarche, pregnancy, breastfeeding)
//   LifestyleFactors (smoking, alcohol, exercise, diet)
//   RiskScore (Gail / Tyrer-Cuzick — calculated after clinical data)
//   SDOH (transportation, language, engagement, barriers)
//   Consent (opt-out status, communication preferences)

// ============================================================
// END OF STEP 1 LOAD SCRIPT
// Next Step: Step 2 — Matching Algorithm
// Match each eligible member to one of 51 Ideal Personas
// ============================================================
