"""
Neo4j schema setup — BCS Care Gap Knowledge Graph
Creates constraints and indexes for all node types.
"""

CONSTRAINTS = [
    "CREATE CONSTRAINT IF NOT EXISTS FOR (m:Member) REQUIRE m.memberID IS UNIQUE",
    "CREATE CONSTRAINT IF NOT EXISTS FOR (e:Enrollment) REQUIRE e.enrollmentID IS UNIQUE",
    "CREATE CONSTRAINT IF NOT EXISTS FOR (b:BenefitPlan) REQUIRE b.planID IS UNIQUE",
    "CREATE CONSTRAINT IF NOT EXISTS FOR (s:ScreeningRecord) REQUIRE s.screeningID IS UNIQUE",
    "CREATE CONSTRAINT IF NOT EXISTS FOR (c:Claim) REQUIRE c.claimID IS UNIQUE",
    "CREATE CONSTRAINT IF NOT EXISTS FOR (g:CareGap) REQUIRE g.careGapID IS UNIQUE",
    "CREATE CONSTRAINT IF NOT EXISTS FOR (o:Outreach) REQUIRE o.outreachID IS UNIQUE",
    "CREATE CONSTRAINT IF NOT EXISTS FOR (p:Provider) REQUIRE p.npi IS UNIQUE",
    "CREATE CONSTRAINT IF NOT EXISTS FOR (q:QualityMeasure) REQUIRE q.measureID IS UNIQUE",
    "CREATE CONSTRAINT IF NOT EXISTS FOR (cm:CareManager) REQUIRE cm.careManagerID IS UNIQUE",
    "CREATE CONSTRAINT IF NOT EXISTS FOR (p:Persona) REQUIRE p.personaID IS UNIQUE",
]

# Node labels and their key fields (for documentation)
NODE_SCHEMA = {
    "Member": [
        "memberID", "fullName"
    ],
    "Demographics": [
        "demographicsID", "dateOfBirth", "age", "genderAdministrative",
        "genderSexAtBirth", "genderSexParamClinical", "address", "state",
        "zipCode", "employmentStatus", "healthLiteracyLevel"
    ],
    "Enrollment": [
        "enrollmentID", "enrollmentStartDate",
        "enrollmentEndDate", "continuouslyEnrolled", "enrollmentGapInPeriod",
        "disenrolled", "measurementYear", "lookbackStart", "lookbackEnd",
        "proactiveLookbackStart"
    ],
    "BenefitPlan": [
        "planID", "planType", "payerName", "groupID", "mammogramCoverage", "deductibleMet", "copay"
    ],
    "Vitals": [
        "systolic", "diastolic", "weightLbs", "heightCm", "bmi",
        "heartRate", "temperature", "vitalDate"
    ],
    "ClinicalHistory": [
        "personalHistoryBreastCancer", "familyHistoryBreastCancer",
        "familyHistoryRelation", "familyHistoryAgeAtDiagnosis",
        "brcaMutationStatus", "priorBreastBiopsy", "biopsyDate", "biopsyResult",
        "denseBreastTissue", "biradsCategory", "chestRadiationHistory",
        "chestRadiationAge", "comorbidities", "mentalHealthConditions",
        "immunocompromised"
    ],
    "Medication": [
        "medicationName", "dose", "purpose", "hrtUse", "hrtType",
        "tamoxifenRaloxifeneUse", "bcsRelevanceFlag"
    ],
    "ReproductiveHistory": [
        "ageAtMenarche", "ageAtMenopause", "numberOfPregnancies",
        "ageAtFirstPregnancy", "breastfeedingHistory"
    ],
    "LifestyleFactors": [
        "smokingStatus", "alcoholConsumption", "physicalActivityLevel", "dietType"
    ],
    "ScreeningRecord": [
        "screeningID", "lastMammogramDate", "mammogramType", "icd10Code",
        "cptCode", "cpt77063PairedWith77067", "imagingType", "biradsResult",
        "facilityName", "inNetworkFacility", "fallsWithinLookbackWindow",
        "priorScreeningHistory", "pendingFollowUp"
    ],
    "Claim": [
        "claimID", "claimType", "cptCodeOnClaim", "icd10OnClaim",
        "serviceDate", "claimStatus", "inNetworkClaim", "outOfNetworkClaimFound",
        "claimSource", "mriUsed", "ultrasoundUsed", "biopsyUsed", "cadAloneUsed",
        "hedisBCSCompliance", "measurementYear"
    ],
    "Provider": [
        "npi", "providerName", "specialty", "lastVisitDate",
        "orderedMammogram", "facilityType", "referralIssued",
        "telehealthVisitsLast12Months", "oncologistAssigned"
    ],
    "Exclusion": [
        "bilateralMastectomy", "unilateralMastectomyLeft", "unilateralMastectomyRight",
        "twoUnilateralMastectomies", "hospicePalliativeCare", "deceased",
        "frailtyAdvancedIllness", "medicare66InLTC", "genderAffirmingChestSurgery",
        "excluded"
    ],
    "RiskScore": [
        "fiveYearRiskScore", "lifetimeRiskScore", "riskModelUsed",
        "recommendedScreeningType"
    ],
    "SDOH": [
        "transportationAccess", "distanceToFacilityMiles", "facilityAvgWaitDays",
        "languagePreference", "preferredContactMethod", "bestTimeToContact",
        "engagementScore", "knownBarrier", "priorNonComplianceReason"
    ],
    "CareGap": [
        "careGapID", "measureID", "gapStatus", "gapCreatedDate",
        "gapClosedDate", "priorityLevel", "priorityReason", "careManagerAssigned"
    ],
    "Outreach": [
        "outreachID", "careGapID", "careManagerID", "channel",
        "outreachDate", "outreachStatus", "followUpDate", "outcome"
    ],
    "Consent": [
        "optOutOfOutreach", "hipaaConsentOnFile",
        "communicationConsent", "deceased"
    ],
    "QualityMeasure": [
        "measureID", "measureName", "description"
    ],
    "CareManager": [
        "careManagerID", "careManagerName", "specialty", "contactInfo"
    ],
    "IdealPersona": ["personaID", "personaName", "group"],
    "AgeRuleCheck": ["eligibilityAgeCheck", "lookbackAgeCheck", "medicare66PlusInSNP_LTC"],
    "EnrollmentProfile": ["continuouslyEnrolled", "enrollmentGapPresent"],
    "ScreeningProfile": ["screeningStatus", "monthsSinceLastScreen", "lastMammogramType", "cptValid", "claimType", "fallsInLookbackWindow"],
    "RiskProfile": ["brcaStatus", "familyHistory", "denseBreast", "hrtUse", "bmi", "priorBiopsy", "earlyMenarche", "firstPregnancyAfter30", "noBreastfeeding", "sedentary", "alcoholUse"],
    "ComorbidityProfile": ["hasComorbidities", "comorbidityTypes", "mentalHealthCondition"],
    "ExclusionProfile": ["bilateralMastectomy", "hospice", "palliativeCare", "frailty", "genderAffirmingSurgery", "anyExclusionPresent"],
    "EngagementProfile": ["engagementLevel", "knownBarrier", "preferredContact", "transportationAccess"],
    "CareGapOutput": ["gapStatus", "priorityLevel", "priorityReason", "riskCategory", "recommendedScreeningType", "recommendedActions", "outreachChannel", "escalationPath", "followUpDays"]
}

RELATIONSHIPS = [
    ("Member", "HAS_DEMOGRAPHICS", "Demographics"),
    ("Member", "HAS_ENROLLMENT", "Enrollment"),
    ("Member", "ENROLLED_IN", "BenefitPlan"),
    ("Member", "HAS_VITALS", "Vitals"),
    ("Member", "HAS_CLINICAL_HISTORY", "ClinicalHistory"),
    ("Member", "TAKES_MEDICATION", "Medication"),
    ("Member", "HAS_REPRODUCTIVE_HISTORY", "ReproductiveHistory"),
    ("Member", "HAS_LIFESTYLE", "LifestyleFactors"),
    ("Member", "HAS_SCREENING", "ScreeningRecord"),
    ("Member", "HAS_CLAIM", "Claim"),
    ("Member", "ASSIGNED_TO_PROVIDER", "Provider"),
    ("Member", "HAS_EXCLUSION", "Exclusion"),
    ("Member", "HAS_RISK_SCORE", "RiskScore"),
    ("Member", "HAS_SDOH", "SDOH"),
    ("Member", "HAS_CARE_GAP", "CareGap"),
    ("Member", "HAS_CONSENT", "Consent"),
    ("CareGap", "HAS_OUTREACH", "Outreach"),
    ("CareGap", "MEASURES", "QualityMeasure"),
    ("CareGap", "ASSIGNED_TO", "CareManager"),
    ("Outreach", "PERFORMED_BY", "CareManager"),
    ("IdealPersona", "HAS_AGE_RULE", "AgeRuleCheck"),
    ("IdealPersona", "HAS_ENROLLMENT", "EnrollmentProfile"),
    ("IdealPersona", "HAS_SCREENING", "ScreeningProfile"),
    ("IdealPersona", "HAS_RISK", "RiskProfile"),
    ("IdealPersona", "HAS_COMORBIDITY", "ComorbidityProfile"),
    ("IdealPersona", "HAS_EXCLUSION", "ExclusionProfile"),
    ("IdealPersona", "HAS_ENGAGEMENT", "EngagementProfile"),
    ("IdealPersona", "HAS_CARE_GAP_OUTPUT", "CareGapOutput"),
]


def apply_schema(driver):
    with driver.session() as session:
        for constraint in CONSTRAINTS:
            session.run(constraint)
    print("✅ Schema constraints applied.")
