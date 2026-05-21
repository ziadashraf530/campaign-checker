import { useEffect, useRef, useState } from 'react'
import axios from 'axios'
import ReviewQueue from './review_queue.jsx'
import MediaReviewModal from './media_review_modal.jsx'

const t = {
  en: {
    title: "Campaign Checker",
    subtitle: "Next-gen visual verification & campaign matching platform",
    engineActive: "SigLIP v1.2 Engine Active",
    tabWorkstation: "Workstation",
    tabQueue: "QA Review Queue",
    tabBatch: "Batch Ingestion",
    controlCenter: "Control Center",
    apiPort: "API Server Port",
    siglipMatcher: "SigLIP Matcher",
    legacyAnalyzer: "Legacy Analyzer",
    refDir: "Reference Campaign Directory",
    targetPath: "Target File or Folder Path",
    campaignTag: "Campaign Tag / Name",
    autoScrub: "Auto-Scrub OCR Overlay Blocks",
    verifyCompliance: "Verify Compliance Text & Brief",
    selectBrief: "Select Campaign Brief Template",
    captionPlaceholder: "Insert post caption here...",
    captionLabel: "Caption Text & Hashtags",
    rulesPlaceholder: "Enter campaign rules (one per line)...",
    rulesLabel: "Campaign Compliance Rules",
    runEngine: "Run Matching Engine",
    resultsTitle: "Visual Verification Results",
    clearBtn: "Clear",
    statusSummary: "Status Summary",
    totalScanned: "Total Scanned",
    matchesFound: "Matches Found",
    avgConfidence: "Average Confidence",
    avgVisualScore: "Average Visual Score",
    complianceAvg: "Compliance Average",
    originalMedia: "Original Media",
    socialPlatform: "Social Media Platform",
    verificationStatus: "Verification Category Status",
    reviewerSignature: "Reviewer Signature (Identity)",
    reviewNotes: "Review Notes / Audit Annotations",
    ignoredUiText: "Ignored UI Text Elements",
    subtitlesText: "Subtitles / Text Overlay",
    complianceStatus: "Caption compliance status",
    complianceRulesBreakdown: "Compliance Rule Details",
    passedChecks: "Passed Checks",
    violations: "Violations",
    warnings: "Warnings",
    batchTitle: "Batch Ingestion",
    batchSubtitle: "Queue multiple campaign targets for background visual analysis without blocking the browser.",
    liveBatchTelemetry: "Live Batch Telemetry",
    launchAsyncBatch: "Launch Async Batch",
    processingBatch: "Processing Batch...",
    batchComplete: "Batch complete! Switch to",
    batchCompleteToInspect: "to inspect results.",
    referencesLoaded: "references loaded",
    campaignMatchReport: "Campaign Match Report",
    totalTargets: "Total Targets",
    strongMatches: "Strong Matches",
    possibleMatches: "Possible Matches",
    rejections: "Rejections",
    varianceInfo: "Reference bank variance: {variance}. Lower variance indicates highly consistent references (strict threshold).",
    refSetQuality: "Reference Set Quality",
    silhouetteScore: "Silhouette Cohesion Score",
    intraSimMean: "Intra Similarity Mean",
    intraSimStd: "Intra Similarity Std",
    socialUiAnalytics: "Social UI Analytics",
    distTelemetry: "Distribution Telemetry",
    socialMediaLabel: "Social Media",
    verticalFormat: "Vertical Format",
    uiOverlays: "UI / Overlays",
    screenshotsLabel: "Screenshots",
    avgUiBoost: "Avg UI Boost",
    detectedPlatforms: "Detected Platforms",
    postCount: "post",
    postsCount: "posts",
    targetVerificationList: "Target Verification List",
    aspect: "Aspect: ",
    socialFormat: "Social Format",
    overlay: "Overlay",
    noise: "Noise: ",
    offset: "Offset: ",
    similarityMetrics: "Similarity Metrics",
    overallVerdict: "Overall Match Verdict",
    primaryBlendedScore: "Primary Blended Score",
    maxSimilarityFound: "Max Similarity Found",
    averageSimilarity: "Average Similarity",
    thresholdApplied: "Threshold Applied",
    framesEvaluated: "Frames Evaluated",
    bestReferenceImage: "Best Reference Image",
    computeTime: "Compute Time",
    refMatchingBreakdown: "Reference Matching Breakdown",
    brandConflictProximity: "Brand Conflict & Proximity",
    competitorProximityIndex: "Competitor Proximity Index",
    nearestCompetitor: "Nearest Competitor Asset: ",
    decisionAmbiguityIndex: "Decision Ambiguity Index",
    statusLabel: "Status: ",
    ambiguousMatch: "AMBIGUOUS MATCH PATTERN",
    highRetrievalMargin: "HIGH RETRIEVAL MARGIN",
    diagnosticsLogs: "Diagnostic & Explainability Logs",
    allDiagnosticsNominal: "All Retrieval Diagnostics Nominal:",
    nominalDesc: "Verification metrics confirmed clear decision boundaries. No competitor distractor encroachment detected.",
    plattCalibration: "Platt scaling calibration",
    calibratedProb: "Calibrated Probability",
    rawMaxSim: "Raw Max Similarity",
    rawAvgSim: "Raw Avg Similarity",
    activeThreshold: "Active Threshold",
    decisionMargin: "Decision Margin",
    temporalStabilityInfo: "Temporal stability info",
    temporalContinuityStrength: "Temporal Continuity Strength",
    stableSegmentsCount: "Stable Segments Count",
    bestMatchFrameId: "Best Match Frame ID",
    diagnosticsStatus: "Diagnostics Status",
    warningsFlagged: "WARNINGS FLAGGED",
    nominal: "NOMINAL",
    semanticCluster: "Semantic Cluster & Adjustments",
    dominantCluster: "Dominant Cluster Group",
    logoRefs: "Logo References",
    drinkRefs: "Drink References",
    productRefs: "Product References",
    storeRefs: "Store References",
    globalCentroid: "Global Centroid",
    clusterCentroidSim: "Cluster Centroid Similarity",
    socialUiAdjustment: "Social UI Adjustment",
    brandingProductBoost: "Branding Product Boost",
    calibrationAdjustments: "Calibration Adjustments",
    activeBoosts: "ACTIVE BOOSTS",
    modelDecisionChain: "Model Decision Reasoning Chain",
    stepPrefix: "Step ",
    temporalTimelineChart: "Temporal Verification & Retrieval Timeline",
    thrLabel: "THR: ",
    frameLabel: "Frame: ",
    rawScoreLabel: "Raw Score: ",
    smoothedLabel: "Smoothed: ",
    competitorProximityLabel: "Competitor Proximity: ",
    bestRefLabel: "Best Reference: ",
    rawFrameScore: "Raw Frame Score",
    smoothedMatchScore: "Smoothed Match Score",
    competitorProximityLabelLegend: "Competitor Proximity",
    matchThresholdLabelLegend: "Match Threshold",
    segmentLabel: "Segment ",
    extractedFrameAnalysis: "Extracted Frame Analysis",
    ocrComplianceTitle: "OCR & Caption Compliance Analysis",
    complianceGrade: "Compliance Grade",
    violationsPts: "Violations (-20 pts each)",
    critical: "CRITICAL",
    ocr: "OCR",
    caption: "Caption",
    both: "Both",
    warningsPts: "Warnings (-10 pts each)",
    warning: "WARNING",
    info: "INFO",
    extractedOcrText: "Extracted OCR Overlay Text",
    ocrDiagnosticLogs: "OCR Diagnostic Logs & Reasoning Chain",
    clickToExpand: "Click to Expand / Collapse",
    captionComplianceNotEvaluated: "Caption Compliance Not Evaluated:",
    captionComplianceNotEvaluatedDesc: "Caption analysis is only performed for successful campaign matching posts when caption text and brief compliance rules are provided.",
    legacyResultsHeader: "Legacy Analysis Results",
    post: "Post",
    platform: "Platform",
    complete: "Complete",
    failed: "Failed",
    referenceCampaignDir: "Reference Campaign Directory",
    targetMediaFolderOrFile: "Target Media Folder or File",
    campaignTagLabel: "Campaign Tag",
    apiPortLabel: "API Port",
    captionTextLabel: "Caption Text",
    campaignRulesLabel: "Campaign Compliance Rules",
    processingBatchLabel: "Processing Batch...",
    launchAsyncBatchLabel: "Launch Async Batch",
    liveTelemetryLabel: "Live Batch Telemetry",
    batchCompleteLabel: "Batch complete! Switch to ",
    qaReviewQueue: "QA Review Queue",
    toInspectResults: " to inspect results.",
    strongMatch: "Strong Match",
    probableMatch: "Probable Match",
    possibleMatch: "Possible Match",
    noMatch: "No Match",
    compliancePass: "Caption: PASS",
    compliancePartial: "Caption: PARTIAL",
    complianceFail: "Caption: FAIL",
    socialRatio: "Social Ratio"
  },
  ar: {
    title: "مُحقق الحملات",
    subtitle: "منصة تحقق بصري وتطابق حملات متطورة وممتازة",
    engineActive: "محرك السِيجْ-لِيبْ v1.2 شغال ونشط",
    tabWorkstation: "منصة العمل اليدوي",
    tabQueue: "طابور مراجعة الجودة",
    tabBatch: "الاستيراد بالدفعة",
    controlCenter: "مركز التحكم والضبط",
    apiPort: "منفذ خادم الـ API",
    siglipMatcher: "مطابق SigLIP الذكي",
    legacyAnalyzer: "محلل الإرث القديم",
    refDir: "مجلد الحملة المرجعية",
    targetPath: "مسار ملف أو مجلد الهدف",
    campaignTag: "علامة / اسم الحملة",
    autoScrub: "مسح وتصفية تراكبات الـ OCR تلقائياً",
    verifyCompliance: "التحقق من نصوص الامتثال وشروط الحملة",
    selectBrief: "اختر قالب شروط الحملة الجاهز",
    captionPlaceholder: "أدخل النص المنشور هنا...",
    captionLabel: "نص الوصف والهاشتاجات المرافقة",
    rulesPlaceholder: "أدخل الشروط (شرط واحد في كل سطر)...",
    rulesLabel: "شروط وقواعد امتثال الحملة",
    runEngine: "تشغيل محرك التطابق البصري",
    resultsTitle: "نتائج التحقق البصري المكتشفة",
    clearBtn: "مسح الكل",
    statusSummary: "ملخص حالة الفحص البصري",
    totalScanned: "إجمالي المفحوص",
    matchesFound: "التطابقات المكتشفة",
    avgConfidence: "متوسط نسبة الثقة",
    avgVisualScore: "متوسط النتيجة البصرية",
    complianceAvg: "متوسط امتثال النصوص",
    originalMedia: "المادة الأصلية المعروضة",
    socialPlatform: "منصة التواصل المكتشفة",
    verificationStatus: "حالة فئة التحقق الحالية",
    reviewerSignature: "توقيع المراجع البشري (الهوية)",
    reviewNotes: "ملاحظات وتجاوزات مراجعة الجودة",
    ignoredUiText: "عناصر واجهة المستخدم المهملة (UI)",
    subtitlesText: "الترجمات وتراكب النصوص المكتشفة",
    complianceStatus: "حالة امتثال النص والوصف المرافق",
    complianceRulesBreakdown: "تفاصيل قواعد الامتثال وشروطه",
    passedChecks: "الفحوصات المقبولة (ناجح)",
    violations: "المخالفات المكتشفة (راسب)",
    warnings: "التحذيرات الصادرة",
    batchTitle: "الاستيراد ومعالجة الدفعات",
    batchSubtitle: "ضع أهداف حملات متعددة في الطابور للتحليل البصري في الخلفية بدون حجب المتصفح علطول.",
    liveBatchTelemetry: "بيانات القياس عن بُعد للدفعات الحية في الخلفية",
    launchAsyncBatch: "إطلاق الدفعة غير المتزامنة",
    processingBatch: "جاري معالجة الدفعة دلوقتي...",
    batchComplete: "الدفعة خلصت وجاهزة! انقل على",
    batchCompleteToInspect: "علشان تشوف وتراجع النتائج.",
    referencesLoaded: "مراجع تم تحميلها",
    campaignMatchReport: "تقرير تطابق الحملة البصري",
    totalTargets: "إجمالي الأهداف المفحوصة",
    strongMatches: "تطابقات قوية (مية مية)",
    possibleMatches: "تطابقات محتملة (على الحركرك)",
    rejections: "مرفوضات (مرفوض خالص)",
    varianceInfo: "تباين المجموعات المرجعية: {variance}. التباين المنخفض يعني مرجعيات متناسقة جداً وصارمة.",
    refSetQuality: "جودة المجموعات المرجعية",
    silhouetteScore: "معامل تماسك الصورة الظلية (Silhouette)",
    intraSimMean: "متوسط التشابه الداخلي",
    intraSimStd: "الانحراف المعياري للتشابه الداخلي",
    socialUiAnalytics: "تحليلات واجهة شبكات التواصل",
    distTelemetry: "بيانات توزيع واجهات العرض",
    socialMediaLabel: "شبكات اجتماعية",
    verticalFormat: "تنسيق رأسي (9:16)",
    uiOverlays: "عناصر واجهة وتراكبات",
    screenshotsLabel: "لقطات شاشة",
    avgUiBoost: "متوسط زيادة عناصر الواجهة",
    detectedPlatforms: "المنصات المكتشفة",
    postCount: "منشور واحد",
    postsCount: "منشورات",
    targetVerificationList: "قائمة التحقق للأهداف البصرية",
    aspect: "الأبعاد: ",
    socialFormat: "تنسيق شبكة",
    overlay: "تراكب",
    noise: "الضوضاء: ",
    offset: "إزاحة: ",
    similarityMetrics: "مؤشرات التشابه البصري",
    overallVerdict: "قرار التطابق البصري النهائي",
    primaryBlendedScore: "النتيجة المختلطة الأساسية",
    maxSimilarityFound: "أعلى نسبة تشابه مكتشفة",
    averageSimilarity: "متوسط نسبة التشابه",
    thresholdApplied: "الحد الأدنى المطبق",
    framesEvaluated: "عدد اللقطات التي تم فحصها",
    bestReferenceImage: "أفضل صورة مرجعية مطابقة",
    computeTime: "زمن الفحص والمعالجة",
    refMatchingBreakdown: "تفاصيل مطابقة الصور المرجعية",
    brandConflictProximity: "تداخل العلامات وقرب المنافسين",
    competitorProximityIndex: "مؤشر مدى قرب شعار المنافس",
    nearestCompetitor: "أقرب أصل منافس مكتشف: ",
    decisionAmbiguityIndex: "مؤشر غموض القرار البصري",
    statusLabel: "الحالة: ",
    ambiguousMatch: "نمط تطابق غامض وغير واضح",
    highRetrievalMargin: "هامش استرجاع بصري ممتاز وآمن",
    diagnosticsLogs: "سجلات التشخيص وتفسير القرارات",
    allDiagnosticsNominal: "كل تشخيصات الاسترجاع البصري سليمة وممتازة:",
    nominalDesc: "مقاييس التحقق أكدت وجود حدود قرار واضحة وجلية. لم يتم الكشف عن أي تعدي أو تشويش من المنافسين.",
    plattCalibration: "معايرة مقياس بلات (الاحتمالية الموزونة)",
    calibratedProb: "الاحتمالية الموزونة المعايرة",
    rawMaxSim: "التشابه الأقصى الخام",
    rawAvgSim: "التشابه المتوسط الخام",
    activeThreshold: "الحد النشط المعتمد",
    decisionMargin: "هامش القرار البصري",
    temporalStabilityInfo: "بيانات الاستقرار الزمني للفيديو",
    temporalContinuityStrength: "قوة الاستمرارية الزمنية للعلامة",
    stableSegmentsCount: "عدد الأجزاء المستقرة المكتشفة",
    bestMatchFrameId: "رقم اللقطة الأكثر تطابقاً",
    diagnosticsStatus: "حالة الفحوصات والتشخيصات",
    warningsFlagged: "تنبيهات وتحذيرات صادرة",
    nominal: "سليم وطبيعي (تمام التمام)",
    semanticCluster: "مجموعات المعاني والتعديلات الموائمة",
    dominantCluster: "مجموعة الفئة المهيمنة",
    logoRefs: "مراجع الشعارات",
    drinkRefs: "مراجع المشروبات",
    productRefs: "مراجع المنتجات البصرية",
    storeRefs: "مراجع المتاجر والفروع",
    globalCentroid: "المركز العام للمجموعة",
    clusterCentroidSim: "تشابه مركز الفئة البصرية",
    socialUiAdjustment: "تعديل واجهة شبكات التواصل",
    brandingProductBoost: "زيادة العلامة البصرية للمنتج",
    calibrationAdjustments: "تعديلات المعايرة المطبقة",
    activeBoosts: "زيادات ونشاطات مطبقة",
    modelDecisionChain: "سلسلة تفسير منطق قرار النموذج",
    stepPrefix: "خطوة ",
    temporalTimelineChart: "خط زمني للاسترجاع والتحقق البصري",
    thrLabel: "الحد: ",
    frameLabel: "اللقطة: ",
    rawScoreLabel: "النتيجة الخام: ",
    smoothedLabel: "الموزونة: ",
    competitorProximityLabel: "قرب المنافس: ",
    bestRefLabel: "أفضل مرجع: ",
    rawFrameScore: "النتيجة الخام للقطة",
    smoothedMatchScore: "نتيجة التطابق الموزون",
    competitorProximityLabelLegend: "قرب العلامة المنافسة",
    matchThresholdLabelLegend: "حد القبول المطبق",
    segmentLabel: "القسم ",
    extractedFrameAnalysis: "تحليل اللقطات المستخرجة بالتفصيل",
    ocrComplianceTitle: "تحليل امتثال نصوص الـ OCR والوصف المنشور",
    complianceGrade: "درجة الامتثال والالتزام",
    violationsPts: "المخالفات الصارخة (-20 نقطة لكل منها)",
    critical: "صارم وعالي الأهمية",
    ocr: "تراكب بصري",
    caption: "نص منشور",
    both: "كلاهما",
    warningsPts: "تحذيرات قابلة للتفادي (-10 نقاط لكل منها)",
    warning: "تحذير",
    info: "معلوماتية",
    extractedOcrText: "نصوص تراكب الـ OCR المستخرجة",
    ocrDiagnosticLogs: "سجلات تشخيص الـ OCR وسلسلة المعالجة",
    clickToExpand: "انقر للتوسيع / الإغلاق اليدوي",
    captionComplianceNotEvaluated: "لم يتم فحص وامتثال النص والهاشتاجات بعد",
    captionComplianceNotEvaluatedDesc: "يتم إجراء تحليل امتثال النصوص فقط للمنشورات المطابقة بصرياً بنجاح عندما تتوفر نصوص النشر وشروط وقواعد الحملة المطلوبة.",
    legacyResultsHeader: "نتائج التحليل البصري القديم المكتشفة",
    post: "منشور",
    platform: "المنصة المكتشفة",
    complete: "مكتمل بنجاح",
    failed: "فشل في المعالجة",
    referenceCampaignDir: "مجلد الحملة المرجعية المعتمدة",
    targetMediaFolderOrFile: "ملف أو مجلد محتوى الهدف البصري",
    campaignTagLabel: "علامة / اسم الحملة المعتمد",
    apiPortLabel: "منفذ خادم الـ API للمطابقة",
    captionTextLabel: "نص الوصف والهاشتاجات المرفقة",
    campaignRulesLabel: "شروط وقواعد امتثال الحملة البصرية",
    processingBatchLabel: "جاري معالجة الدفعة دلوقتي...",
    launchAsyncBatchLabel: "إطلاق الدفعة غير المتزامنة",
    liveTelemetryLabel: "لوحة قياس الدفعة الحية بالخلفية",
    batchCompleteLabel: "خلصت الدفعة بالكامل! انقل على ",
    qaReviewQueue: "طابور مراجعة الجودة والالتزام",
    toInspectResults: " علشان تشوف وتراجع النتائج اللي طلعت.",
    strongMatch: "تطابق قوي (مية مية)",
    probableMatch: "تطابق محتمل وقوي",
    possibleMatch: "تطابق محتمل (على الحركرك)",
    noMatch: "مرفوض خالص (لا تطابق)",
    compliancePass: "الوصف: مقبول (تمام)",
    compliancePartial: "الوصف: مقبول جزئياً",
    complianceFail: "الوصف: مخالف (مرفوض)",
    socialRatio: "نسبة منصات التواصل"
  }
};

export default function App() {
  const [mode, setMode] = useState('siglip') // 'siglip' or 'legacy'
  
  // SigLIP Form refs
  const siglipRefPathRef = useRef(null)
  const siglipTargetPathRef = useRef(null)
  const siglipCampaignNameRef = useRef(null)
  const [siglipDebug, setSiglipDebug] = useState(false)
  
  // Legacy Form refs
  const legacyBrandRef = useRef(null)
  const legacyTargetPathRef = useRef(null)
  const legacyRefPathRef = useRef(null)

  // Global app states
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [siglipData, setSiglipData] = useState(null)
  const [legacyResults, setLegacyResults] = useState([])
  const [expandedCards, setExpandedCards] = useState({})
  const [apiPort, setApiPort] = useState('8001')
  const [siglipCaption, setSiglipCaption] = useState('Best coffee ever ☕ Try Starbucks today! #StarbucksPartner @Starbucks')
  const [siglipRules, setSiglipRules] = useState('- must mention @Starbucks\n- must include #StarbucksPartner\n- no competitor mentions\n- avoid overly promotional wording')
  const [templates, setTemplates] = useState([])
  const [selectedTemplate, setSelectedTemplate] = useState('')

  // ── QA Workstation & Review Queue workflow state ──────────────
  const [mainTab, setMainTab] = useState('workstation') // 'workstation' | 'queue' | 'batch'
  const [selectedSession, setSelectedSession] = useState(null)
  const [refreshQueueTrigger, setRefreshQueueTrigger] = useState(0)
  const [asyncTask, setAsyncTask] = useState(null)
  const pollingRef = useRef(null)
  const [lang, setLang] = useState('en')

  useEffect(() => {
    const fetchTemplates = async () => {
      try {
        const res = await axios.get(`http://127.0.0.1:${apiPort}/brief-templates/`)
        setTemplates(res.data || [])
      } catch (err) {
        console.error("Failed to fetch templates:", err)
      }
    }
    fetchTemplates()
  }, [apiPort])

  const toggleExpandCard = (index) => {
    setExpandedCards(prev => ({
      ...prev,
      [index]: !prev[index]
    }))
  }

  const runSiglipMatching = async () => {
    const refPath = siglipRefPathRef.current ? siglipRefPathRef.current.value.trim() : ''
    const targetPath = siglipTargetPathRef.current ? siglipTargetPathRef.current.value.trim() : ''
    const campaignName = siglipCampaignNameRef.current ? siglipCampaignNameRef.current.value.trim() : 'campaign'

    if (!refPath || !targetPath) {
      setError('Please provide both the reference images folder and target file/folder path.')
      return
    }

    setLoading(true)
    setError(null)
    setSiglipData(null)
    setExpandedCards({})

    try {
      const payload = {
        reference_path: refPath,
        target_path: targetPath,
        campaign_name: campaignName,
        debug: siglipDebug,
        caption: siglipCaption,
        rules: siglipRules
      }

      const res = await axios.post(`http://127.0.0.1:${apiPort}/campaign-match/`, payload)
      
      if (res.data.error) {
        setError(res.data.error)
      } else {
        setSiglipData(res.data)
      }
    } catch (err) {
      setError('Connection failed: ' + (err.response?.data?.detail || err.message))
    } finally {
      setLoading(false)
    }
  }

  const runLegacyAnalysis = async () => {
    const brand = legacyBrandRef.current ? legacyBrandRef.current.value.trim() : ''
    const targetPath = legacyTargetPathRef.current ? legacyTargetPathRef.current.value.trim() : ''
    const refPath = legacyRefPathRef.current ? legacyRefPathRef.current.value.trim() : ''

    if (!brand) {
      setError('Please provide a brand name for analysis.')
      return
    }

    setLoading(true)
    setError(null)
    setLegacyResults([])

    try {
      const payload = {
        brand_name: brand
      }
      if (targetPath) payload.target_path = targetPath
      if (refPath) payload.reference_path = refPath

      const res = await axios.post(`http://127.0.0.1:${apiPort}/run-analysis/`, payload)
      
      if (res.data.error) {
        setError(res.data.error)
      } else {
        const results = res.data.results || []
        setLegacyResults(results)
        if (results.length === 0) {
          setError('No posts found to analyze. Check files and paths.')
        }
      }
    } catch (err) {
      setError('Connection failed: ' + (err.response?.data?.detail || err.message))
    } finally {
      setLoading(false)
    }
  }

  // ── Async / Batch matching with real-time telemetry polling ────────
  const stopPolling = () => {
    if (pollingRef.current) {
      clearInterval(pollingRef.current)
      pollingRef.current = null
    }
  }

  const runSiglipMatchAsync = async () => {
    const refPath = siglipRefPathRef.current ? siglipRefPathRef.current.value.trim() : ''
    const targetPath = siglipTargetPathRef.current ? siglipTargetPathRef.current.value.trim() : ''
    const campaignName = siglipCampaignNameRef.current ? siglipCampaignNameRef.current.value.trim() : 'campaign'

    if (!refPath || !targetPath) {
      setError('Please provide both the reference images folder and target file/folder path.')
      return
    }

    setError(null)
    stopPolling()

    try {
      const payload = {
        reference_path: refPath,
        target_path: targetPath,
        campaign_name: campaignName,
        debug: siglipDebug,
        caption: siglipCaption,
        rules: siglipRules
      }
      const res = await axios.post(`http://127.0.0.1:${apiPort}/campaign-match/async/`, payload)
      const taskId = res.data.task_id
      setAsyncTask({ task_id: taskId, polling: true, progress: 0, stage: 'Queuing batch...', status: 'INITIALIZING' })

      pollingRef.current = setInterval(async () => {
        try {
          const prog = await axios.get(`http://127.0.0.1:${apiPort}/campaign-match/progress/${taskId}`)
          const d = prog.data
          setAsyncTask(prev => ({ ...prev, progress: d.progress, stage: d.stage, status: d.status }))
          if (d.status === 'COMPLETED' || d.status === 'FAILED') {
            stopPolling()
            setAsyncTask(prev => ({ ...prev, polling: false }))
            setRefreshQueueTrigger(p => p + 1)
          }
        } catch (pollErr) {
          stopPolling()
        }
      }, 1500)
    } catch (err) {
      setError('Async batch failed: ' + (err.response?.data?.detail || err.message))
    }
  }

  // Cleanup polling interval on component unmount
  useEffect(() => { return () => stopPolling() }, []) // eslint-disable-line react-hooks/exhaustive-deps

  // Determine file type icon
  const getFileTypeIcon = (filename) => {
    if (!filename) return <i className="fa-solid fa-file file-type-icon"></i>
    const ext = filename.split('.').pop().toLowerCase()
    if (['mp4', 'avi', 'mov', 'mkv', 'webm'].includes(ext)) {
      return <i className="fa-solid fa-video file-type-icon video"></i>
    }
    return <i className="fa-solid fa-image file-type-icon"></i>
  }

  // Format verdict display for results
  const renderVerdictBadge = (matchType) => {
    switch (matchType) {
      case 'STRONG_MATCH':
        return <span className="badge strong"><i className="fa-solid fa-circle-check"></i> {labels.strongMatch}</span>
      case 'PROBABLE_STRONG_MATCH':
        return <span className="badge probable"><i className="fa-solid fa-circle-check"></i> {labels.probableMatch}</span>
      case 'POSSIBLE_MATCH':
        return <span className="badge possible"><i className="fa-solid fa-circle-question"></i> {labels.possibleMatch}</span>
      default:
        return <span className="badge none"><i className="fa-solid fa-circle-xmark"></i> {labels.noMatch}</span>
    }
  }

  // Format compliance display for results
  const renderComplianceBadge = (status) => {
    switch (status) {
      case 'PASS':
        return <span className="badge-compliance pass"><i className="fa-solid fa-circle-check"></i> {labels.compliancePass}</span>
      case 'PARTIAL':
        return <span className="badge-compliance partial"><i className="fa-solid fa-triangle-exclamation"></i> {labels.compliancePartial}</span>
      case 'FAIL':
        return <span className="badge-compliance fail"><i className="fa-solid fa-circle-xmark"></i> {labels.complianceFail}</span>
      default:
        return null;
    }
  }

  // Get matching classification CSS state
  const getMatchClass = (matchType) => {
    if (matchType === 'STRONG_MATCH') return 'strong';
    if (matchType === 'PROBABLE_STRONG_MATCH') return 'probable';
    if (matchType === 'POSSIBLE_MATCH') return 'possible';
    return 'none';
  }

  const labels = t[lang] || t.en;

  return (
    <div className={`app-container ${lang === 'ar' ? 'rtl' : ''}`}>
      {/* Top Header */}
      <header>
        <div className="logo-section">
          <h1><i className="fa-solid fa-bolt-lightning"></i> {labels.title}</h1>
          <p>{labels.subtitle}</p>
        </div>
        <div className="header-controls">
          <div className="lang-switcher">
            <button 
              className={`lang-btn ${lang === 'en' ? 'active' : ''}`} 
              onClick={() => setLang('en')}
            >
              English
            </button>
            <button 
              className={`lang-btn ${lang === 'ar' ? 'active' : ''}`} 
              onClick={() => setLang('ar')}
              style={{ fontFamily: 'Cairo, Tajawal, sans-serif' }}
            >
              مصري
            </button>
          </div>
          <div className="engine-badge">
            <span></span> {labels.engineActive}
          </div>
        </div>
      </header>

      {/* ── Main Navigation Tabs ───────────────────────────────────── */}
      <nav className="main-tabs-nav">
        <button
          id="tab-workstation"
          className={`main-tab-btn ${mainTab === 'workstation' ? 'active' : ''}`}
          onClick={() => setMainTab('workstation')}
        >
          <i className="fa-solid fa-wand-magic-sparkles"></i> {labels.tabWorkstation}
        </button>
        <button
          id="tab-queue"
          className={`main-tab-btn ${mainTab === 'queue' ? 'active' : ''}`}
          onClick={() => setMainTab('queue')}
        >
          <i className="fa-solid fa-list-check"></i> {labels.tabQueue}
        </button>
        <button
          id="tab-batch"
          className={`main-tab-btn ${mainTab === 'batch' ? 'active' : ''}`}
          onClick={() => setMainTab('batch')}
        >
          <i className="fa-solid fa-layer-group"></i> {labels.tabBatch}
        </button>
      </nav>

      {/* ── WORKSTATION DASHBOARD TAB ────────────────────────────── */}
      {mainTab === 'workstation' && (
      <main className="dashboard-grid">
        
        {/* Left Side: Parameters / Control Panel */}
        <section className="panel-card">
          <h2><i className="fa-solid fa-sliders"></i> {labels.controlCenter}</h2>

          {/* API Server Port Config */}
          <div className="form-group" style={{ marginBottom: '1.25rem' }}>
            <label>{labels.apiPort}</label>
            <div className="input-wrapper">
              <input 
                type="text"
                className="form-control"
                placeholder="e.g. 8001"
                value={apiPort}
                onChange={(e) => setApiPort(e.target.value.trim())}
              />
              <i className="fa-solid fa-server"></i>
            </div>
          </div>
          
          {/* Mode Selector Tab */}
          <div className="mode-selector">
            <button 
              className={`mode-btn ${mode === 'siglip' ? 'active' : ''}`}
              onClick={() => { setMode('siglip'); setError(null); }}
            >
              <i className="fa-solid fa-fingerprint"></i> {labels.siglipMatcher}
            </button>
            <button 
              className={`mode-btn ${mode === 'legacy' ? 'active' : ''}`}
              onClick={() => { setMode('legacy'); setError(null); }}
            >
              <i className="fa-solid fa-magnifying-glass"></i> {labels.legacyAnalyzer}
            </button>
          </div>

          {/* Mode-specific forms */}
          {mode === 'siglip' ? (
            <div>
              <div className="form-group">
                <label>{labels.refDir}</label>
                <div className="input-wrapper">
                  <input 
                    ref={siglipRefPathRef}
                    className="form-control"
                    placeholder="e.g. data/reference_camp"
                    defaultValue="data/reference"
                  />
                  <i className="fa-solid fa-folder-open"></i>
                </div>
              </div>

              <div className="form-group">
                <label>{labels.targetPath}</label>
                <div className="input-wrapper">
                  <input 
                    ref={siglipTargetPathRef}
                    className="form-control"
                    placeholder="e.g. data/influencer_post.mp4"
                    defaultValue="data"
                  />
                  <i className="fa-solid fa-bullseye"></i>
                </div>
              </div>

              <div className="form-group">
                <label>{labels.campaignTag}</label>
                <div className="input-wrapper">
                  <input 
                    ref={siglipCampaignNameRef}
                    className="form-control"
                    placeholder="e.g. summer_promo_2026"
                    defaultValue="summer_promo"
                  />
                  <i className="fa-solid fa-tag"></i>
                </div>
              </div>

              <div className="form-group">
                <label><i className="fa-solid fa-file-lines" style={{ marginRight: '0.35rem', color: 'var(--accent-light)' }}></i>{labels.selectBrief}</label>
                <div className="input-wrapper">
                  <select
                    className="form-control template-selector"
                    value={selectedTemplate}
                    onChange={(e) => {
                      const name = e.target.value
                      setSelectedTemplate(name)
                      if (name) {
                        const tpl = templates.find(t => t.name === name)
                        if (tpl) {
                          setSiglipCaption(tpl.caption || '')
                          setSiglipRules(tpl.rules || '')
                        }
                      }
                    }}
                  >
                    <option value="">{lang === 'ar' ? '— اختر شروط جاهزة للحملة —' : '— Select a predefined brief —'}</option>
                    {templates.map(t => (
                      <option key={t.name} value={t.name}>{t.name}</option>
                    ))}
                  </select>
                  <i className="fa-solid fa-clipboard-list"></i>
                </div>
              </div>

              <div className="form-group">
                <label>{labels.captionLabel}</label>
                <textarea 
                  className="form-control"
                  style={{ height: '70px', padding: '0.75rem 1rem', resize: 'vertical' }}
                  placeholder={labels.captionPlaceholder}
                  value={siglipCaption}
                  onChange={(e) => setSiglipCaption(e.target.value)}
                />
              </div>

              <div className="form-group">
                <label>{labels.rulesLabel}</label>
                <textarea 
                  className="form-control"
                  style={{ height: '90px', padding: '0.75rem 1rem', resize: 'vertical', fontFamily: 'var(--font-mono)', fontSize: '0.85rem' }}
                  placeholder={labels.rulesPlaceholder}
                  value={siglipRules}
                  onChange={(e) => setSiglipRules(e.target.value)}
                />
              </div>

              <label className="checkbox-group">
                <input 
                  type="checkbox"
                  checked={siglipDebug}
                  onChange={(e) => setSiglipDebug(e.target.checked)}
                />
                <div className="custom-checkbox"></div>
                <span>{lang === 'ar' ? 'تصدير ملفات التشخيص للباك إند' : 'Export debug files to backend'}</span>
              </label>

              <button 
                className="btn-primary" 
                onClick={runSiglipMatching}
                disabled={loading}
              >
                {loading ? (
                  <>
                    <i className="fa-solid fa-circle-notch fa-spin"></i> {lang === 'ar' ? 'جاري التحليل والتدقيق البصري...' : 'Analyzing...'}
                  </>
                ) : (
                  <>
                    <i className="fa-solid fa-wand-magic-sparkles"></i> {labels.runEngine}
                  </>
                )}
              </button>
            </div>
          ) : (
            <div>
              <div className="form-group">
                <label>{lang === 'ar' ? 'اسم الماركة للبحث عنها' : 'Brand Name to Search'}</label>
                <div className="input-wrapper">
                  <input 
                    ref={legacyBrandRef}
                    className="form-control"
                    placeholder="e.g. Nike, Coca-Cola"
                    defaultValue=""
                  />
                  <i className="fa-solid fa-copyright"></i>
                </div>
              </div>

              <div className="form-group">
                <label>{lang === 'ar' ? 'الملف أو المجلد المستهدف (اختياري)' : 'Target File or Folder (Optional)'}</label>
                <div className="input-wrapper">
                  <input 
                    ref={legacyTargetPathRef}
                    className="form-control"
                    placeholder="e.g. data"
                    defaultValue=""
                  />
                  <i className="fa-solid fa-file-invoice"></i>
                </div>
              </div>

              <div className="form-group">
                <label>{lang === 'ar' ? 'مسار الشعارات المرجعية (اختياري)' : 'Reference Logos Path (Optional)'}</label>
                <div className="input-wrapper">
                  <input 
                    ref={legacyRefPathRef}
                    className="form-control"
                    placeholder="e.g. data/logos"
                    defaultValue=""
                  />
                  <i className="fa-solid fa-images"></i>
                </div>
              </div>

              <button 
                className="btn-primary" 
                onClick={runLegacyAnalysis}
                disabled={loading}
              >
                {loading ? (
                  <>
                    <i className="fa-solid fa-circle-notch fa-spin"></i> {lang === 'ar' ? 'جاري فحص الشعارات المكتشفة...' : 'Scanning Logos...'}
                  </>
                ) : (
                  <>
                    <i className="fa-solid fa-search"></i> {lang === 'ar' ? 'تشغيل تحليل الشعارات' : 'Run Logo Analysis'}
                  </>
                )}
              </button>
            </div>
          )}

          {error && (
            <div className="error-banner">
              <i className="fa-solid fa-triangle-exclamation"></i>
              <span>{error}</span>
            </div>
          )}
        </section>

        {/* Right Side: Results Panel */}
        <section className="display-panel">
          
          {/* State 1: Loading */}
          {loading && (
            <div className="loading-panel">
              <div className="loading-spinner"></div>
              <h3>{lang === 'ar' ? 'جاري تشغيل محرك الذكاء الاصطناعي...' : 'AI Engine In Progress'}</h3>
              <p>{lang === 'ar' ? 'جاري استخراج لقطات الفيديو، توليد تضمينات SigLIP البصرية، وحساب جيب تمام التشابه للميزات المتعددة...' : 'Extracting keyframes, generating SigLIP embeddings, and computing multi-factor cosine similarities...'}</p>
            </div>
          )}

          {/* State 2: Welcome / Empty */}
          {!loading && !siglipData && legacyResults.length === 0 && (
            <div className="empty-state">
              <i className="fa-solid fa-robot empty-state-icon"></i>
              <h3>{lang === 'ar' ? 'جاهز للتحقق والتدقيق البصري' : 'Ready for Verification'}</h3>
              <p>{lang === 'ar' ? 'اضبط المجلد المرجعي والأهداف في مركز التحكم والضبط، ثم اضغط تشغيل للحصول على نتائج التحليل والتقارير الموثقة.' : 'Configure your reference campaign directory and targets in the Control Center, then execute verification to receive structured visual reports.'}</p>
            </div>
          )}

          {/* State 3: SigLIP Results Display */}
          {!loading && siglipData && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
              {/* Summary Metrics Card */}
              <div className="summary-card">
                <div className="summary-header">
                  <div className="summary-title">
                    <h3>{labels.campaignMatchReport}</h3>
                    <span>{siglipData.summary?.campaign_name || (lang === 'ar' ? 'تحقق وفحص' : 'Verification')}</span>
                  </div>
                  <div className="engine-badge" style={{ borderColor: 'var(--accent-muted)' }}>
                    {siglipData.summary?.num_references} {labels.referencesLoaded}
                  </div>
                </div>

                <div className="summary-stats">
                  <div className="stat-item">
                    <div className="stat-val accent">{siglipData.summary?.num_targets}</div>
                    <div className="stat-label">{labels.totalTargets}</div>
                  </div>
                  <div className="stat-item">
                    <div className="stat-val strong">{siglipData.summary?.strong_matches}</div>
                    <div className="stat-label">{labels.strongMatches}</div>
                  </div>
                  <div className="stat-item">
                    <div className="stat-val possible">{siglipData.summary?.possible_matches}</div>
                    <div className="stat-label">{labels.possibleMatches}</div>
                  </div>
                  <div className="stat-item">
                    <div className="stat-val none">{siglipData.summary?.rejections}</div>
                    <div className="stat-label">{labels.rejections}</div>
                  </div>
                </div>

                <div className="info-row">
                  <i className="fa-solid fa-circle-info"></i>
                  <span>
                    {(() => {
                      const parts = labels.varianceInfo.split('{variance}');
                      return (
                        <>
                          {parts[0]}<strong>{siglipData.summary?.reference_variance}</strong>{parts[1]}
                        </>
                      );
                    })()}
                  </span>
                </div>
              </div>

              {/* Reference Set Quality Card */}
              {siglipData.summary?.cohesion_metrics && (
                <div className="cohesion-panel">
                  <div className="cohesion-header">
                    <div className="cohesion-title"><i className="fa-solid fa-gem"></i> {labels.refSetQuality}</div>
                    <span className={`cohesion-quality-badge ${siglipData.summary.cohesion_metrics.cluster_quality?.toLowerCase()}`}>
                      {siglipData.summary.cohesion_metrics.cluster_quality}
                    </span>
                  </div>
                  <div className="cohesion-bar-wrapper">
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
                      <span>{labels.silhouetteScore}</span>
                      <span className="mono">{Math.round(siglipData.summary.cohesion_metrics.silhouette_score * 100)}%</span>
                    </div>
                    <div className="cohesion-bar-track">
                      <div className="cohesion-bar-fill" style={{ width: `${Math.round(siglipData.summary.cohesion_metrics.silhouette_score * 100)}%` }}></div>
                    </div>
                  </div>
                  <div className="calibration-grid" style={{ gridTemplateColumns: '1fr 1fr', marginTop: '0.5rem', borderTop: 'none', paddingTop: '0' }}>
                    <div className="calibration-stat-row" style={{ borderBottom: 'none' }}>
                      <span className="calibration-stat-label" style={{ fontSize: '0.75rem' }}>{labels.intraSimMean}</span>
                      <span className="calibration-stat-val" style={{ fontSize: '0.75rem' }}>{siglipData.summary.cohesion_metrics.intra_similarity_mean?.toFixed(4)}</span>
                    </div>
                    <div className="calibration-stat-row" style={{ borderBottom: 'none' }}>
                      <span className="calibration-stat-label" style={{ fontSize: '0.75rem' }}>{labels.intraSimStd}</span>
                      <span className="calibration-stat-val" style={{ fontSize: '0.75rem' }}>{siglipData.summary.cohesion_metrics.intra_similarity_std?.toFixed(4)}</span>
                    </div>
                  </div>

                  {siglipData.summary.cohesion_metrics.recommendations && (
                    <div className="cohesion-recommendations">
                      {siglipData.summary.cohesion_metrics.recommendations.map((rec, rIdx) => (
                        <div key={rIdx} className="cohesion-recommendation-item">
                          <i className="fa-solid fa-circle-chevron-right"></i>
                          <span>{rec}</span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}

              {/* Social Media Analytics Card */}
              {siglipData.social_analytics && siglipData.social_analytics.total_targets > 0 && (
                <div className="summary-card" style={{ background: 'linear-gradient(135deg, hsl(230, 20%, 11%) 0%, hsl(230, 20%, 8%) 100%)' }}>
                  <div className="summary-header">
                    <div className="summary-title">
                      <h3><i className="fa-solid fa-share-nodes" style={{ color: 'var(--accent-light)' }}></i> {labels.socialUiAnalytics}</h3>
                      <span>{labels.distTelemetry}</span>
                    </div>
                    <div className="engine-badge" style={{ borderColor: 'var(--accent-muted)', color: 'var(--match-probable)' }}>
                      <i className="fa-solid fa-chart-pie"></i> {Math.round(siglipData.social_analytics.social_ratio * 100)}% {labels.socialRatio}
                    </div>
                  </div>

                  <div className="summary-stats" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(110px, 1fr))', gap: '0.75rem' }}>
                    <div className="stat-item">
                      <div className="stat-val" style={{ color: 'var(--accent-light)', fontSize: '1.35rem' }}>
                        {Math.round(siglipData.social_analytics.social_ratio * 100)}%
                      </div>
                      <div className="stat-label" style={{ fontSize: '0.65rem' }}>{labels.socialMediaLabel}</div>
                    </div>
                    <div className="stat-item">
                      <div className="stat-val" style={{ color: 'var(--match-possible)', fontSize: '1.35rem' }}>
                        {Math.round(siglipData.social_analytics.vertical_ratio * 100)}%
                      </div>
                      <div className="stat-label" style={{ fontSize: '0.65rem' }}>{labels.verticalFormat}</div>
                    </div>
                    <div className="stat-item">
                      <div className="stat-val" style={{ color: 'var(--match-none)', fontSize: '1.35rem' }}>
                        {Math.round(siglipData.social_analytics.overlay_ratio * 100)}%
                      </div>
                      <div className="stat-label" style={{ fontSize: '0.65rem' }}>{labels.uiOverlays}</div>
                    </div>
                    <div className="stat-item">
                      <div className="stat-val" style={{ color: 'var(--text-secondary)', fontSize: '1.35rem' }}>
                        {Math.round(siglipData.social_analytics.mobile_screenshot_ratio * 100)}%
                      </div>
                      <div className="stat-label" style={{ fontSize: '0.65rem' }}>{labels.screenshotsLabel}</div>
                    </div>
                    <div className="stat-item">
                      <div className="stat-val" style={{ color: 'var(--match-strong)', fontSize: '1.35rem' }}>
                        +{siglipData.social_analytics.average_social_adjustment?.toFixed(3)}
                      </div>
                      <div className="stat-label" style={{ fontSize: '0.65rem' }}>{labels.avgUiBoost}</div>
                    </div>
                  </div>

                  {siglipData.social_analytics.platform_distribution && Object.keys(siglipData.social_analytics.platform_distribution).length > 0 && (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', borderTop: '1px dashed var(--border-color)', paddingTop: '0.75rem' }}>
                      <div style={{ fontSize: '0.75rem', fontWeight: '700', textTransform: 'uppercase', color: 'var(--text-muted)', letterSpacing: '0.05em' }}>
                        {labels.detectedPlatforms}
                      </div>
                      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem' }}>
                        {Object.entries(siglipData.social_analytics.platform_distribution).map(([platform, count]) => {
                          let platformLabel = platform.replace('_', ' ').toUpperCase();
                          let platformIcon = "fa-solid fa-globe";
                          if (platform === 'tiktok') { platformIcon = "fa-brands fa-tiktok"; }
                          else if (platform === 'instagram') { platformIcon = "fa-brands fa-instagram"; }
                          else if (platform === 'facebook') { platformIcon = "fa-brands fa-facebook"; }
                          else if (platform === 'youtube_shorts') { platformIcon = "fa-brands fa-youtube"; platformLabel = "YT SHORTS"; }
                          
                          return (
                            <span key={platform} className="media-badge highlight" style={{ fontSize: '0.75rem', padding: '0.3rem 0.6rem' }}>
                              <i className={platformIcon}></i> {platformLabel}: {count} {count === 1 ? labels.postCount : labels.postsCount}
                            </span>
                          );
                        })}
                      </div>
                    </div>
                  )}
                </div>
              )}

              {/* Individual Target Cards list */}
              <div className="results-header">{labels.targetVerificationList}</div>
              <div className="results-list">
                {siglipData.results?.map((res, index) => {
                  const isExpanded = !!expandedCards[index]
                  const verdictClass = res.match_type
                  
                  return (
                    <div className={`result-card ${verdictClass}`} key={index}>
                      <div className="result-main" onClick={() => toggleExpandCard(index)}>
                        <div className="result-meta">
                          <div className="file-info">
                            {getFileTypeIcon(res.filename)}
                            <div style={{ display: 'flex', flexDirection: 'column', minWidth: 0 }}>
                              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap' }}>
                                <span className="file-name">{res.filename || 'Target Content'}</span>
                                {renderVerdictBadge(res.match_type)}
                                {renderComplianceBadge(res.compliance_status)}
                              </div>
                              {res.media_context && (
                                <div className="media-badges-row">
                                  <span className="media-badge">
                                    <i className="fa-solid fa-expand"></i> {labels.aspect}{res.media_context.aspect_ratio?.toFixed(2)}
                                  </span>
                                  {res.media_context.is_social_media && (
                                    <span className="media-badge highlight">
                                      <i className="fa-solid fa-share-nodes"></i> {labels.socialFormat}
                                    </span>
                                  )}
                                  {res.media_context.has_overlays && (
                                    <span className="media-badge warning">
                                      <i className="fa-solid fa-rectangle-ad"></i> {labels.overlay}
                                    </span>
                                  )}
                                  {res.media_context.compression_level > 0.4 && (
                                    <span className="media-badge">
                                      <i className="fa-solid fa-compress"></i> {labels.noise}{Math.round(res.media_context.compression_level * 100)}%
                                    </span>
                                  )}
                                  {res.media_context.suggested_threshold_offset < 0 && (
                                    <span className="media-badge highlight">
                                      <i className="fa-solid fa-sliders"></i> {labels.offset}{res.media_context.suggested_threshold_offset?.toFixed(2)}
                                    </span>
                                  )}
                                </div>
                              )}
                            </div>
                          </div>
                          <span className="file-path">{res.file}</span>
                        </div>

                        <div className="score-section">
                          <div className="gauge-wrapper">
                            <span className={`gauge-pct ${res.match_type === 'STRONG_MATCH' ? 'strong' : res.match_type === 'POSSIBLE_MATCH' ? 'possible' : 'none'}`}>
                              {res.confidence_pct}%
                            </span>
                            <div className="gauge-track">
                              <div 
                                className={`gauge-fill ${res.match_type === 'STRONG_MATCH' ? 'strong' : res.match_type === 'POSSIBLE_MATCH' ? 'possible' : 'none'}`}
                                style={{ width: `${res.confidence_pct}%` }}
                              ></div>
                            </div>
                          </div>

                          <button className={`expand-btn ${isExpanded ? 'active' : ''}`}>
                            <i className="fa-solid fa-chevron-down"></i>
                          </button>
                        </div>
                      </div>

                      {/* Expandable detailed statistics box */}
                      {isExpanded && (
                        <div className="result-details">
                          {/* Top Row: Metrics & References */}
                          <div className="detail-row">
                            {/* Similarity Metrics */}
                            <div>
                              <div className="detail-section-title">
                                <i className="fa-solid fa-chart-line"></i> {labels.similarityMetrics}
                              </div>
                              <div className="matching-highlights">
                                <div className="highlight-box">
                                  <span className="highlight-label">{labels.overallVerdict}</span>
                                  <span className="highlight-val">{res.verdict}</span>
                                </div>
                                <div className="highlight-box">
                                  <span className="highlight-label">{labels.primaryBlendedScore}</span>
                                  <span className="highlight-val mono">{(res.confidence).toFixed(4)}</span>
                                </div>
                                <div className="highlight-box">
                                  <span className="highlight-label">{labels.maxSimilarityFound}</span>
                                  <span className="highlight-val mono">{(res.top_similarity).toFixed(4)}</span>
                                </div>
                                <div className="highlight-box">
                                  <span className="highlight-label">{labels.averageSimilarity}</span>
                                  <span className="highlight-val mono">{(res.average_similarity).toFixed(4)}</span>
                                </div>
                                <div className="highlight-box">
                                  <span className="highlight-label">{labels.thresholdApplied}</span>
                                  <span className="highlight-val mono">{(res.threshold_used).toFixed(4)}</span>
                                </div>
                                <div className="highlight-box">
                                  <span className="highlight-label">{labels.framesEvaluated}</span>
                                  <span className="highlight-val">{res.num_frames_analyzed}</span>
                                </div>
                                {res.best_reference && (
                                  <div className="highlight-box">
                                    <span className="highlight-label">{labels.bestReferenceImage}</span>
                                    <span className="highlight-val" style={{ maxWidth: '180px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={res.best_reference}>
                                      {res.best_reference}
                                    </span>
                                  </div>
                                )}
                                <div className="highlight-box">
                                  <span className="highlight-label">{labels.computeTime}</span>
                                  <span className="highlight-val">{res.processing_time_ms} ms</span>
                                </div>
                              </div>
                            </div>

                            {/* Reference Matching Breakdown */}
                            <div>
                              <div className="detail-section-title">
                                <i className="fa-solid fa-cubes"></i> {labels.refMatchingBreakdown}
                              </div>
                              <div className="ref-matches-list">
                                {res.top_matches?.map((ref, rIndex) => (
                                  <div className="ref-match-bar-item" key={rIndex}>
                                    <div className="ref-match-bar-meta">
                                      <span className="ref-name" title={ref.reference_name}>#{ref.rank} {ref.reference_name}</span>
                                      <span className="ref-sim-val">{(ref.similarity * 100).toFixed(1)}%</span>
                                    </div>
                                    <div className="ref-match-bar-track">
                                      <div 
                                        className="ref-match-bar-fill"
                                        style={{ 
                                          width: `${ref.similarity * 100}%`,
                                          background: ref.rank === 1 ? 'var(--accent-light)' : 'var(--accent-muted)' 
                                        }}
                                      ></div>
                                    </div>
                                  </div>
                                ))}
                              </div>
                            </div>
                          </div>

                          {/* Row 2: Brand Overlap & Ambiguity Gauges */}
                          <div className="detail-row">
                            {/* Competitor Overlap Gauges */}
                            <div>
                              <div className="detail-section-title">
                                <i className="fa-solid fa-shield-halved"></i> {labels.brandConflictProximity}
                              </div>
                              <div className="matching-highlights">
                                <div className="highlight-box-vertical">
                                  <div className="highlight-vertical-header">
                                    <span className="highlight-label">{labels.competitorProximityIndex}</span>
                                    <span className="highlight-val mono">{(res.competitor_similarity || 0.0).toFixed(4)}</span>
                                  </div>
                                  <div className="competitor-track">
                                    <div 
                                      className={`competitor-fill ${res.competitor_similarity > 0.70 ? 'danger' : res.competitor_similarity > 0.60 ? 'warning' : 'safe'}`}
                                      style={{ width: `${(res.competitor_similarity || 0.0) * 100}%` }}
                                    ></div>
                                  </div>
                                  {res.explainability?.best_competitor && (
                                    <div className="competitor-meta-info">
                                      {labels.nearestCompetitor}<strong>{res.explainability.best_competitor}</strong>
                                    </div>
                                  )}
                                </div>

                                <div className="highlight-box-vertical">
                                  <div className="highlight-vertical-header">
                                    <span className="highlight-label">{labels.decisionAmbiguityIndex}</span>
                                    <span className="highlight-val mono">{(res.ambiguity_score || 0.0).toFixed(4)}</span>
                                  </div>
                                  <div className="competitor-track">
                                    <div 
                                      className={`competitor-fill ${res.ambiguity_score > 0.60 ? 'danger' : res.ambiguity_score > 0.30 ? 'warning' : 'safe'}`}
                                      style={{ width: `${(res.ambiguity_score || 0.0) * 100}%` }}
                                    ></div>
                                  </div>
                                  <div className="competitor-meta-info">
                                    {labels.statusLabel}<strong className={res.ambiguity_score > 0.5 ? 'txt-danger' : 'txt-safe'}>{res.ambiguity_score > 0.5 ? labels.ambiguousMatch : labels.highRetrievalMargin}</strong>
                                  </div>
                                </div>
                              </div>
                            </div>

                            {/* Diagnostics Panel & Warnings */}
                            <div>
                              <div className="detail-section-title">
                                <i className="fa-solid fa-stethoscope"></i> {labels.diagnosticsLogs}
                              </div>
                              
                              {res.warnings && res.warnings.length > 0 ? (
                                <div className="diagnostic-warnings-container">
                                  {res.warnings.map((warn, wIdx) => (
                                    <div key={wIdx} className="diagnostic-warning-bar">
                                      <i className="fa-solid fa-triangle-exclamation warning-icon"></i>
                                      <div className="warning-text">{warn}</div>
                                    </div>
                                  ))}
                                </div>
                              ) : (
                                <div className="diagnostic-success-bar">
                                  <i className="fa-solid fa-circle-check success-icon"></i>
                                  <div className="success-text">
                                    <strong>{labels.allDiagnosticsNominal}</strong> {labels.nominalDesc}
                                  </div>
                                </div>
                              )}
                            </div>
                          </div>

                          {/* Platt Calibration / Temporal Stability Grid */}
                          <div className="calibration-grid">
                            {/* Calibration Card 1: Platt scaling */}
                            <div className="calibration-card">
                               <div className="calibration-card-header">
                                <i className="fa-solid fa-chart-line"></i> {labels.plattCalibration}
                              </div>
                              <div className="calibration-stat-row">
                                <span className="calibration-stat-label">{labels.calibratedProb}</span>
                                <span className={`calibration-stat-val ${res.match_type === 'STRONG_MATCH' ? 'highlight-green' : res.match_type === 'PROBABLE_STRONG_MATCH' ? 'highlight-gold' : ''}`}>
                                  {res.confidence_pct}%
                                </span>
                              </div>
                              <div className="calibration-stat-row">
                                <span className="calibration-stat-label">{labels.rawMaxSim}</span>
                                <span className="calibration-stat-val">{res.top_similarity?.toFixed(4)}</span>
                              </div>
                              <div className="calibration-stat-row">
                                <span className="calibration-stat-label">{labels.rawAvgSim}</span>
                                <span className="calibration-stat-val">{res.average_similarity?.toFixed(4)}</span>
                              </div>
                              <div className="calibration-stat-row">
                                <span className="calibration-stat-label">{labels.activeThreshold}</span>
                                <span className="calibration-stat-val">{res.threshold_used?.toFixed(4)}</span>
                              </div>
                              <div className="calibration-stat-row">
                                <span className="calibration-stat-label">{labels.decisionMargin}</span>
                                <span className="calibration-stat-val">{(res.confidence - res.threshold_used)?.toFixed(4)}</span>
                              </div>
                            </div>

                            {/* Calibration Card 2: Temporal Stability */}
                            <div className="calibration-card">
                               <div className="calibration-card-header">
                                <i className="fa-solid fa-clock-rotate-left"></i> {labels.temporalStabilityInfo}
                              </div>
                              <div className="calibration-stat-row">
                                <span className="calibration-stat-label">{labels.temporalContinuityStrength}</span>
                                <span className="calibration-stat-val highlight-green">
                                  {(res.temporal_strength || 0.0)?.toFixed(4)}
                                </span>
                              </div>
                              <div className="calibration-stat-row">
                                <span className="calibration-stat-label">{labels.framesEvaluated}</span>
                                <span className="calibration-stat-val">{res.num_frames_analyzed}</span>
                              </div>
                              <div className="calibration-stat-row">
                                <span className="calibration-stat-label">{labels.stableSegmentsCount}</span>
                                <span className="calibration-stat-val">{res.stable_segments ? res.stable_segments.length : 0}</span>
                              </div>
                              <div className="calibration-stat-row">
                                <span className="calibration-stat-label">{labels.bestMatchFrameId}</span>
                                <span className="calibration-stat-val" style={{ maxWidth: '160px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={res.best_frame}>
                                  {res.best_frame || 'N/A'}
                                </span>
                              </div>
                              <div className="calibration-stat-row">
                                <span className="calibration-stat-label">{labels.diagnosticsStatus}</span>
                                <span className="calibration-stat-val">{res.warnings && res.warnings.length > 0 ? labels.warningsFlagged : labels.nominal}</span>
                              </div>
                            </div>

                            {/* Calibration Card 3: Reference Cluster & Boost Telemetry */}
                            <div className="calibration-card">
                              <div className="calibration-card-header">
                                <i className="fa-solid fa-cubes"></i> {labels.semanticCluster}
                              </div>
                              <div className="calibration-stat-row">
                                <span className="calibration-stat-label">{labels.dominantCluster}</span>
                                <span className="calibration-stat-val" style={{ color: 'var(--accent-light)' }}>
                                  {(() => {
                                    const cl = res.dominant_cluster;
                                    if (cl === 'logo_refs') return labels.logoRefs;
                                    if (cl === 'drink_refs') return labels.drinkRefs;
                                    if (cl === 'product_refs') return labels.productRefs;
                                    if (cl === 'store_refs') return labels.storeRefs;
                                    return cl || labels.globalCentroid;
                                  })()}
                                </span>
                              </div>
                              <div className="calibration-stat-row">
                                <span className="calibration-stat-label">{labels.clusterCentroidSim}</span>
                                <span className="calibration-stat-val">
                                  {res.cluster_similarity !== undefined && res.cluster_similarity !== null ? res.cluster_similarity.toFixed(4) : '0.0000'}
                                </span>
                              </div>
                              <div className="calibration-stat-row">
                                <span className="calibration-stat-label">{labels.socialUiAdjustment}</span>
                                <span className={`calibration-stat-val ${res.social_adjustment > 0 ? 'highlight-green' : ''}`}>
                                  {res.social_adjustment > 0 ? `+${res.social_adjustment.toFixed(3)}` : '0.000'}
                                </span>
                              </div>
                              <div className="calibration-stat-row">
                                <span className="calibration-stat-label">{labels.brandingProductBoost}</span>
                                <span className={`calibration-stat-val ${res.product_boost > 0 ? 'highlight-green' : ''}`}>
                                  {res.product_boost > 0 ? `+${res.product_boost.toFixed(3)}` : '0.000'}
                                </span>
                              </div>
                              <div className="calibration-stat-row">
                                <span className="calibration-stat-label">{labels.calibrationAdjustments}</span>
                                <span className="calibration-stat-val">
                                  {res.social_adjustment > 0 || res.product_boost > 0 ? labels.activeBoosts : labels.nominal}
                                </span>
                              </div>
                            </div>
                          </div>

                          {/* Model Decision Reasoning Chain */}
                          {res.explainability?.reasoning_steps && (
                            <div>
                              <div className="detail-section-title">
                                <i className="fa-solid fa-brain"></i> {labels.modelDecisionChain}
                              </div>
                              <div className="reasoning-list">
                                {res.explainability.reasoning_steps.map((step, sIdx) => {
                                  let iconClass = 'fa-solid fa-circle-info';
                                  let statusClass = '';
                                  if (step.includes('CONFIRMED')) {
                                    iconClass = 'fa-solid fa-circle-check';
                                    statusClass = 'success';
                                  } else if (step.includes('REJECTED') || step.includes('WARNING') || step.includes('High brand conflict')) {
                                    iconClass = 'fa-solid fa-triangle-exclamation';
                                    statusClass = 'warning';
                                  } else if (sIdx === 0) {
                                    iconClass = 'fa-solid fa-database';
                                    statusClass = 'active';
                                  } else if (sIdx === 1) {
                                    iconClass = 'fa-solid fa-video';
                                    statusClass = 'active';
                                  } else if (step.includes('Highest similarity') || step.includes('similarity found')) {
                                    iconClass = 'fa-solid fa-bullseye';
                                    statusClass = 'active';
                                  } else if (step.includes('calibrated')) {
                                    iconClass = 'fa-solid fa-calculator';
                                    statusClass = 'active';
                                  }
                                  
                                  const parts = step.split(': ');
                                  const title = parts.length > 1 && parts[0].length < 30 ? parts[0] : `${labels.stepPrefix}${sIdx + 1}`;
                                  const desc = parts.length > 1 && parts[0].length < 30 ? parts.slice(1).join(': ') : step;

                                  return (
                                    <div key={sIdx} className="reasoning-step-item">
                                      <div className={`reasoning-step-icon ${statusClass}`}>
                                        <i className={iconClass}></i>
                                      </div>
                                      <div className="reasoning-step-content">
                                        <span className="reasoning-step-title">{title}</span>
                                        <span className="reasoning-step-desc">{desc}</span>
                                      </div>
                                    </div>
                                  );
                                })}
                              </div>
                            </div>
                          )}

                          {/* Row 3: Video Temporal Timeline SVG Chart */}
                          {res.num_frames_analyzed > 1 && res.frame_scores && res.frame_scores.length > 1 && (
                            <div className="timeline-section">
                              <div className="detail-section-title">
                                <i className="fa-solid fa-chart-area"></i> {labels.temporalTimelineChart}
                              </div>
                              
                              <div className="timeline-svg-wrapper">
                                <svg viewBox="0 0 800 160" width="100%" height="160" className="timeline-svg">
                                  <defs>
                                    <filter id="glow-smooth" x="-20%" y="-20%" width="140%" height="140%">
                                      <feGaussianBlur stdDeviation="3" result="blur" />
                                      <feComposite in="SourceGraphic" in2="blur" operator="over" />
                                    </filter>
                                    <linearGradient id="grid-grad" x1="0" y1="0" x2="0" y2="1">
                                      <stop offset="0%" stopColor="var(--border-color)" stopOpacity="0.1" />
                                      <stop offset="100%" stopColor="var(--border-color)" stopOpacity="0.3" />
                                    </linearGradient>
                                  </defs>
                                  
                                  {/* Grid lines and background */}
                                  <rect x="50" y="20" width="700" height="100" fill="url(#grid-grad)" rx="4" />
                                  
                                  {/* Horizontal grid lines */}
                                  {[0, 0.25, 0.5, 0.75, 1.0].map((level, lIdx) => {
                                    const y = 120 - (level * 100);
                                    return (
                                      <g key={lIdx}>
                                        <line x1="50" y1={y} x2="750" y2={y} stroke="var(--border-color)" strokeWidth="0.5" strokeDasharray={level === 0 || level === 1 ? "0" : "4,4"} />
                                        <text x="20" y={y + 4} fill="var(--text-muted)" fontSize="9" fontFamily="var(--font-mono)" textAnchor="start">{level.toFixed(2)}</text>
                                      </g>
                                    )
                                  })}
                                  
                                  {/* Match Threshold line */}
                                  {(() => {
                                    const yThresh = 120 - (res.threshold_used * 100);
                                    return (
                                      <g>
                                        <line x1="50" y1={yThresh} x2="750" y2={yThresh} stroke="var(--match-possible)" strokeWidth="1.5" strokeDasharray="3,3" />
                                        <text x="755" y={yThresh + 3} fill="var(--match-possible)" fontSize="9" fontWeight="bold">{labels.thrLabel}{res.threshold_used.toFixed(2)}</text>
                                      </g>
                                    )
                                  })()}
                                  
                                  {/* Vertical frame dividers */}
                                  {res.frame_scores.map((frame, i) => {
                                    const x = 50 + (i * 700) / (res.frame_scores.length - 1);
                                    return (
                                      <line key={i} x1={x} y1="20" x2={x} y2="120" stroke="var(--border-color)" strokeWidth="0.25" />
                                    )
                                  })}

                                  {/* SVG Paths */}
                                  {/* Raw / Max similarity curve */}
                                  <path 
                                    d={res.frame_scores.map((frame, i) => {
                                      const x = 50 + (i * 700) / (res.frame_scores.length - 1);
                                      const score = frame.raw_score !== undefined ? frame.raw_score : frame.max_similarity;
                                      const y = 120 - (score * 100);
                                      return `${i === 0 ? 'M' : 'L'} ${x} ${y}`;
                                    }).join(" ")} 
                                    fill="none" 
                                    stroke="var(--accent-muted)" 
                                    strokeWidth="1.5" 
                                    strokeDasharray="3,3" 
                                    opacity="0.75" 
                                  />
                                  
                                  {/* Competitor similarity curve */}
                                  <path 
                                    d={res.frame_scores.map((frame, i) => {
                                      const x = 50 + (i * 700) / (res.frame_scores.length - 1);
                                      const score = frame.competitor_similarity !== undefined ? frame.competitor_similarity : 0.0;
                                      const y = 120 - (score * 100);
                                      return `${i === 0 ? 'M' : 'L'} ${x} ${y}`;
                                    }).join(" ")} 
                                    fill="none" 
                                    stroke="var(--match-none)" 
                                    strokeWidth="1.75" 
                                    strokeDasharray="4,2" 
                                  />
                                  
                                  {/* Smoothed campaign similarity curve */}
                                  <path 
                                    d={res.frame_scores.map((frame, i) => {
                                      const x = 50 + (i * 700) / (res.frame_scores.length - 1);
                                      const score = frame.smoothed_similarity !== undefined ? frame.smoothed_similarity : frame.max_similarity;
                                      const y = 120 - (score * 100);
                                      return `${i === 0 ? 'M' : 'L'} ${x} ${y}`;
                                    }).join(" ")} 
                                    fill="none" 
                                    stroke="var(--match-strong)" 
                                    strokeWidth="3.5" 
                                    strokeLinecap="round"
                                    strokeLinejoin="round"
                                    filter="url(#glow-smooth)" 
                                  />
                                  
                                  {/* Interactive circles */}
                                  {res.frame_scores.map((frame, i) => {
                                    const x = 50 + (i * 700) / (res.frame_scores.length - 1);
                                    const smVal = frame.smoothed_similarity !== undefined ? frame.smoothed_similarity : frame.max_similarity;
                                    const ySmooth = 120 - (smVal * 100);
                                    const isMatched = smVal >= res.threshold_used;
                                    
                                    return (
                                      <g key={i} className="timeline-node-group">
                                        <circle 
                                          cx={x} 
                                          cy={ySmooth} 
                                          r="4.5" 
                                          fill={isMatched ? "var(--match-strong)" : "var(--bg-dark)"} 
                                          stroke={isMatched ? "var(--text-primary)" : "var(--match-none)"}
                                          strokeWidth="1.5" 
                                        />
                                        <title>{`${labels.frameLabel}${frame.frame_id}\n${labels.rawScoreLabel}${(frame.raw_score !== undefined ? frame.raw_score : frame.max_similarity).toFixed(3)}\n${labels.smoothedLabel}${smVal.toFixed(3)}\n${labels.competitorProximityLabel}${(frame.competitor_similarity !== undefined ? frame.competitor_similarity : 0.0).toFixed(3)}\n${labels.bestRefLabel}${frame.best_reference}`}</title>
                                      </g>
                                    )
                                  })}
                                </svg>
                              </div>
                              
                              {/* Dynamic Legend */}
                              <div className="timeline-legend">
                                <div className="legend-item"><span className="legend-dot raw"></span> {labels.rawFrameScore}</div>
                                <div className="legend-item"><span className="legend-dot smoothed"></span> {labels.smoothedMatchScore}</div>
                                <div className="legend-item"><span className="legend-dot competitor"></span> {labels.competitorProximityLabelLegend}</div>
                                <div className="legend-item"><span className="legend-dot thresh"></span> {labels.matchThresholdLabelLegend}</div>
                              </div>

                              {/* Active Matching Timeline Segment Pills */}
                              {res.stable_segments && res.stable_segments.length > 0 && (
                                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem', marginTop: '0.75rem', justifyContent: 'center' }}>
                                  {res.stable_segments.map((seg, sIdx) => (
                                    <span key={sIdx} className="media-badge highlight" style={{ fontSize: '0.8rem', padding: '0.35rem 0.65rem' }}>
                                      <i className="fa-solid fa-circle-play"></i> {labels.segmentLabel}{sIdx + 1}: Frames {seg.start_frame}-{seg.end_frame} ({seg.duration_frames}f) | Avg: {(seg.average_score * 100).toFixed(1)}%
                                    </span>
                                  ))}
                                </div>
                              )}
                            </div>
                          )}

                          {/* Row 4: Keyframe List */}
                          {res.num_frames_analyzed > 1 && res.frame_scores && res.frame_scores.length > 0 && (
                            <div className="keyframes-section">
                              <div className="detail-section-title">
                                <i className="fa-solid fa-photo-film"></i> {labels.extractedFrameAnalysis}
                              </div>
                              <div className="keyframes-grid">
                                {res.frame_scores.map((frame, fIndex) => (
                                  <div className="keyframe-card" key={fIndex}>
                                    <div className="keyframe-id" title={frame.frame_id}>{frame.frame_id}</div>
                                    <div className="keyframe-score">{(frame.max_similarity * 100).toFixed(1)}%</div>
                                    <div className="keyframe-ref" title={frame.best_reference}>ref: {frame.best_reference}</div>
                                  </div>
                                ))}
                              </div>
                            </div>
                          )}

                          {/* Caption & Brief Compliance Analysis */}
                          <div className="compliance-panel">
                            <div className="detail-section-title">
                              <i className="fa-solid fa-square-check"></i> {labels.ocrComplianceTitle}
                            </div>
                            
                            {res.compliance_status && res.compliance_status !== 'NOT_EVALUATED' ? (
                              <>
                                <div className="compliance-grid-layout">
                                  {/* Left Side: Score summary */}
                                  <div className="compliance-summary-box">
                                    <div className={`compliance-score-circle ${res.compliance_status.toLowerCase()}`}>
                                      {res.compliance_score}%
                                    </div>
                                    <div className="compliance-status-label">{labels.complianceGrade}</div>
                                    {renderComplianceBadge(res.compliance_status)}
                                  </div>

                                  {/* Right Side: Evaluated rules breakdown */}
                                  <div className="compliance-rules-box">
                                    {/* Violations (Hard Fails) */}
                                    {res.rules_detailed && res.rules_detailed.filter(r => !r.passed && r.severity === 'CRITICAL').length > 0 && (
                                      <div>
                                        <div className="compliance-rule-group-title" style={{ color: 'var(--match-none)' }}>
                                          {labels.violationsPts}
                                        </div>
                                        <div className="compliance-rule-list">
                                          {res.rules_detailed.filter(r => !r.passed && r.severity === 'CRITICAL').map((rule, rIdx) => (
                                            <div key={rIdx} className="compliance-rule-item violation">
                                              <i className="fa-solid fa-circle-xmark"></i>
                                              <div style={{ flex: 1 }}>
                                                <span>{rule.details}</span>
                                                <span className="badge-severity critical">{labels.critical}</span>
                                                {rule.match_source && (
                                                  <span className={`badge-source ${rule.match_source}`}>
                                                    <i className={rule.match_source === 'ocr' ? 'fa-solid fa-camera' : rule.match_source === 'caption' ? 'fa-solid fa-align-left' : 'fa-solid fa-cubes'}></i>
                                                    {rule.match_source === 'ocr' ? labels.ocr : rule.match_source === 'caption' ? labels.caption : labels.both}
                                                  </span>
                                                )}
                                              </div>
                                            </div>
                                          ))}
                                        </div>
                                      </div>
                                    )}

                                    {/* Warnings */}
                                    {res.rules_detailed && res.rules_detailed.filter(r => !r.passed && r.severity === 'WARNING').length > 0 && (
                                      <div style={{ marginTop: res.rules_detailed.filter(r => !r.passed && r.severity === 'CRITICAL').length > 0 ? '0.75rem' : '0' }}>
                                        <div className="compliance-rule-group-title" style={{ color: 'var(--match-possible)' }}>
                                          {labels.warningsPts}
                                        </div>
                                        <div className="compliance-rule-list">
                                          {res.rules_detailed.filter(r => !r.passed && r.severity === 'WARNING').map((rule, rIdx) => (
                                            <div key={rIdx} className="compliance-rule-item warning">
                                              <i className="fa-solid fa-triangle-exclamation"></i>
                                              <div style={{ flex: 1 }}>
                                                <span>{rule.details}</span>
                                                <span className="badge-severity warning">{labels.warning}</span>
                                                {rule.match_source && (
                                                  <span className={`badge-source ${rule.match_source}`}>
                                                    <i className={rule.match_source === 'ocr' ? 'fa-solid fa-camera' : rule.match_source === 'caption' ? 'fa-solid fa-align-left' : 'fa-solid fa-cubes'}></i>
                                                    {rule.match_source === 'ocr' ? labels.ocr : rule.match_source === 'caption' ? labels.caption : labels.both}
                                                  </span>
                                                )}
                                              </div>
                                            </div>
                                          ))}
                                        </div>
                                      </div>
                                    )}

                                    {/* Passed Rules */}
                                    {res.rules_detailed && res.rules_detailed.filter(r => r.passed).length > 0 && (
                                      <div style={{ marginTop: res.rules_detailed.filter(r => !r.passed).length > 0 ? '0.75rem' : '0' }}>
                                        <div className="compliance-rule-group-title" style={{ color: 'var(--match-strong)' }}>
                                          {labels.passedChecks}
                                        </div>
                                        <div className="compliance-rule-list">
                                          {res.rules_detailed.filter(r => r.passed).map((rule, rIdx) => (
                                            <div key={rIdx} className="compliance-rule-item pass">
                                              <i className="fa-solid fa-circle-check"></i>
                                              <div style={{ flex: 1 }}>
                                                <span>{rule.details}</span>
                                                <span className={`badge-severity ${rule.severity?.toLowerCase() || 'info'}`}>{rule.severity || labels.info}</span>
                                                {rule.match_source && (
                                                  <span className={`badge-source ${rule.match_source}`}>
                                                    <i className={rule.match_source === 'ocr' ? 'fa-solid fa-camera' : rule.match_source === 'caption' ? 'fa-solid fa-align-left' : 'fa-solid fa-cubes'}></i>
                                                    {rule.match_source === 'ocr' ? labels.ocr : rule.match_source === 'caption' ? labels.caption : labels.both}
                                                  </span>
                                                )}
                                              </div>
                                            </div>
                                          ))}
                                        </div>
                                      </div>
                                    )}
                                  </div>
                                </div>

                                {/* OCR Extracted Text Bubble List */}
                                {res.ocr_text && res.ocr_text.length > 0 && (
                                  <div className="ocr-extracted-section">
                                    <div className="ocr-extracted-title">
                                      <i className="fa-solid fa-binoculars"></i> Extracted OCR Overlay Text ({res.ocr_text.length})
                                    </div>
                                    <div className="ocr-bubble-list">
                                      {res.ocr_text.map((text, tIdx) => (
                                        <span key={tIdx} className="ocr-bubble">
                                          <i className="fa-solid fa-font"></i> {text}
                                        </span>
                                      ))}
                                    </div>
                                  </div>
                                )}

                                {/* OCR Technical Explainability Logs */}
                                {res.ocr_explainability && (
                                  <details className="ocr-explainability-section">
                                    <summary className="ocr-explainability-header">
                                      <span>
                                        <i className="fa-solid fa-bug" style={{ marginRight: '0.4rem', color: 'var(--accent-light)' }}></i>
                                        OCR Diagnostic Logs & Reasoning Chain
                                      </span>
                                      <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Click to Expand / Collapse</span>
                                    </summary>
                                    <pre className="ocr-explainability-pre">
                                      {res.ocr_explainability}
                                    </pre>
                                  </details>
                                )}
                              </>
                            ) : (
                              <div className="diagnostic-warning-bar" style={{ background: 'var(--bg-dark)' }}>
                                <i className="fa-solid fa-circle-info warning-icon" style={{ color: 'var(--text-muted)' }}></i>
                                <div className="warning-text" style={{ color: 'var(--text-secondary)' }}>
                                  <strong>Caption Compliance Not Evaluated:</strong> Caption analysis is only performed for successful campaign matching posts when caption text and brief compliance rules are provided.
                                </div>
                              </div>
                            )}
                          </div>
                        </div>
                      )}
                    </div>
                  )
                })}
              </div>
            </div>
          )}

          {/* State 4: Legacy results display */}
          {!loading && legacyResults.length > 0 && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
              <div className="results-header">{labels.legacyResultsHeader}</div>
              <div className="results-list">
                {legacyResults.map((r, i) => (
                  <div className="result-card STRONG_MATCH" key={i} style={{ borderLeft: '4px solid var(--accent)' }}>
                    <div className="result-main" style={{ cursor: 'default' }}>
                      <div className="result-meta">
                        <div className="file-info">
                          {getFileTypeIcon(r.file)}
                          <span className="file-name" style={{ maxWidth: '350px' }}>{r.file.split(/[\\/]/).pop()}</span>
                          <span className="badge legacy">{r.influencer || labels.post} ({r.platform || labels.platform})</span>
                        </div>
                        <span className="file-path">{r.file}</span>
                      </div>
                      <div className="score-section" style={{ minWidth: '220px', maxWidth: '350px' }}>
                        <span style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', textAlign: 'right', fontStyle: 'italic' }}>
                          {r.status}
                        </span>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

        </section>
      </main>
      )} {/* end mainTab === 'workstation' */}

      {/* ── QA REVIEW QUEUE TAB ──────────────────────────────── */}
      {mainTab === 'queue' && (
        <main className="queue-main">
          <ReviewQueue
            apiPort={apiPort}
            onOpenWorkstation={(session) => setSelectedSession(session)}
            refreshTrigger={refreshQueueTrigger}
            lang={lang}
          />
        </main>
      )}

      {/* ── BATCH INGESTION TAB ───────────────────────────────── */}
      {mainTab === 'batch' && (
        <main className="batch-main">
          <div className="batch-ingestion-panel">
            <div className="batch-header-row">
              <div>
                <h2><i className="fa-solid fa-layer-group"></i> {labels.batchTitle}</h2>
                <p>{labels.batchSubtitle}</p>
              </div>
              {asyncTask && (
                <span className={`batch-status-pill ${asyncTask.status.toLowerCase()}`}>
                  {asyncTask.status === 'COMPLETED'
                    ? <><i className="fa-solid fa-circle-check"></i> {labels.complete}</>
                    : asyncTask.status === 'FAILED'
                      ? <><i className="fa-solid fa-circle-xmark"></i> {labels.failed}</>
                      : <><i className="fa-solid fa-circle-notch fa-spin"></i> {asyncTask.status}</>
                  }
                </span>
              )}
            </div>

            <div className="batch-form-grid">
              <div className="form-group">
                <label><i className="fa-solid fa-folder-open" style={{ marginRight: '0.35rem', color: 'var(--accent-light)' }}></i> {labels.referenceCampaignDir}</label>
                <div className="input-wrapper">
                  <input ref={siglipRefPathRef} className="form-control" placeholder="e.g. data/reference" defaultValue="data/reference" />
                  <i className="fa-solid fa-folder-open"></i>
                </div>
              </div>
              <div className="form-group">
                <label><i className="fa-solid fa-bullseye" style={{ marginRight: '0.35rem', color: 'var(--accent-light)' }}></i> {labels.targetMediaFolderOrFile}</label>
                <div className="input-wrapper">
                  <input ref={siglipTargetPathRef} className="form-control" placeholder="e.g. data/influencer_posts/" defaultValue="data" />
                  <i className="fa-solid fa-bullseye"></i>
                </div>
              </div>
              <div className="form-group">
                <label><i className="fa-solid fa-tag" style={{ marginRight: '0.35rem', color: 'var(--accent-light)' }}></i> {labels.campaignTagLabel}</label>
                <div className="input-wrapper">
                  <input ref={siglipCampaignNameRef} className="form-control" placeholder="e.g. summer_promo_2026" defaultValue="summer_promo" />
                  <i className="fa-solid fa-tag"></i>
                </div>
              </div>
              <div className="form-group">
                <label><i className="fa-solid fa-server" style={{ marginRight: '0.35rem', color: 'var(--accent-light)' }}></i> {labels.apiPortLabel}</label>
                <div className="input-wrapper">
                  <input type="text" className="form-control" placeholder="8001" value={apiPort} onChange={(e) => setApiPort(e.target.value.trim())} />
                  <i className="fa-solid fa-server"></i>
                </div>
              </div>
            </div>

            <div className="batch-form-grid" style={{ gridTemplateColumns: '1fr' }}>
              <div className="form-group">
                <label>{labels.captionTextLabel}</label>
                <textarea className="form-control" style={{ height: '60px', padding: '0.75rem 1rem', resize: 'vertical' }} placeholder={labels.captionPlaceholder} value={siglipCaption} onChange={(e) => setSiglipCaption(e.target.value)} />
              </div>
              <div className="form-group">
                <label>{labels.campaignRulesLabel}</label>
                <textarea className="form-control" style={{ height: '75px', padding: '0.75rem 1rem', resize: 'vertical', fontFamily: 'var(--font-mono)', fontSize: '0.85rem' }} placeholder={labels.rulesPlaceholder} value={siglipRules} onChange={(e) => setSiglipRules(e.target.value)} />
              </div>
            </div>

            {error && (
              <div className="error-banner">
                <i className="fa-solid fa-triangle-exclamation"></i>
                <span>{error}</span>
              </div>
            )}

            <button id="btn-launch-batch" className="btn-primary batch-run-btn" onClick={runSiglipMatchAsync} disabled={asyncTask?.polling}>
              {asyncTask?.polling
                ? <><i className="fa-solid fa-circle-notch fa-spin"></i> {labels.processingBatch}</>
                : <><i className="fa-solid fa-layer-group"></i> {labels.launchAsyncBatch}</>
              }
            </button>

            {asyncTask && (
              <div className="batch-progress-card">
                <div className="batch-progress-header">
                  <span><i className="fa-solid fa-gauge-high"></i> {labels.liveBatchTelemetry}</span>
                  <span className="mono" style={{ fontSize: '0.85rem' }}>{asyncTask.progress?.toFixed(1)}%</span>
                </div>
                <div className="batch-progress-track">
                  <div
                    className={`batch-progress-fill ${asyncTask.status === 'COMPLETED' ? 'complete' : asyncTask.status === 'FAILED' ? 'failed' : 'active'}`}
                    style={{ width: `${asyncTask.progress || 0}%` }}
                  ></div>
                </div>
                <div className="batch-stage-label">
                  <i className="fa-solid fa-circle-dot stage-dot"></i>
                  {' '}{asyncTask.stage}
                </div>
                {asyncTask.status === 'COMPLETED' && (
                  <div className="batch-complete-cta">
                    <i className="fa-solid fa-party-horn"></i>
                    {' '}{labels.batchComplete}{' '}
                    <button className="link-btn" onClick={() => setMainTab('queue')}>{labels.qaReviewQueue}</button>
                    {' '}{labels.batchCompleteToInspect}
                  </div>
                )}
              </div>
            )}
          </div>
        </main>
      )}

      {/* ── QA WORKSTATION MODAL (mounts over any active tab) ───────────── */}
      {selectedSession && (
        <MediaReviewModal
          session={selectedSession}
          apiPort={apiPort}
          onClose={() => setSelectedSession(null)}
          onSaved={() => setRefreshQueueTrigger(p => p + 1)}
          lang={lang}
        />
      )}
    </div>
  )
}
