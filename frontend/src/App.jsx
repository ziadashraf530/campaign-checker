import { useEffect, useRef, useState } from 'react'
import axios from 'axios'
import MediaReviewModal from './media_review_modal'

const MAX_PROGRESS_LOG = 120

export default function App() {
  const [mode, setMode] = useState(() => {
    return localStorage.getItem('campaign_checker_mode') || 'siglip'
  })
  
  // SigLIP Form refs
  const siglipRefPathRef = useRef(null)
  const siglipTargetPathRef = useRef(null)
  const siglipCampaignNameRef = useRef(null)
  const siglipExcelPathRef = useRef(null)
  const [siglipDebug, setSiglipDebug] = useState(false)
  
  // Legacy Form refs
  const legacyBrandRef = useRef(null)
  const legacyTargetPathRef = useRef(null)
  const legacyRefPathRef = useRef(null)
  const legacyExcelPathRef = useRef(null)

  // Global app states
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [siglipData, setSiglipData] = useState(() => {
    const saved = localStorage.getItem('campaign_checker_siglip_data')
    try {
      return saved ? JSON.parse(saved) : null
    } catch (e) {
      console.error('Error parsing campaign_checker_siglip_data', e)
      return null
    }
  })
  const [legacyResults, setLegacyResults] = useState(() => {
    const saved = localStorage.getItem('campaign_checker_legacy_results')
    try {
      return saved ? JSON.parse(saved) : []
    } catch (e) {
      console.error('Error parsing campaign_checker_legacy_results', e)
      return []
    }
  })
  const [expandedCards, setExpandedCards] = useState({})
  const [apiPort, setApiPort] = useState(() => {
    return localStorage.getItem('campaign_checker_api_port') || '8000'
  })

  // Live Progress States
  const [progressLog, setProgressLog] = useState([])
  const [progressPct, setProgressPct] = useState(0)
  const [progressDetail, setProgressDetail] = useState('')
  const [progressStep, setProgressStep] = useState('')

  // Media review modal state
  const [reviewModalOpen, setReviewModalOpen] = useState(false)
  const [reviewPayload, setReviewPayload] = useState(null)

  // Progress ETA tracking
  const progressStartRef = useRef(null)
  const [etaSeconds, setEtaSeconds] = useState(null)

  // Sync to localStorage
  useEffect(() => {
    if (siglipData) {
      localStorage.setItem('campaign_checker_siglip_data', JSON.stringify(siglipData))
    } else {
      localStorage.removeItem('campaign_checker_siglip_data')
    }
  }, [siglipData])

  useEffect(() => {
    if (legacyResults && legacyResults.length > 0) {
      localStorage.setItem('campaign_checker_legacy_results', JSON.stringify(legacyResults))
    } else {
      localStorage.removeItem('campaign_checker_legacy_results')
    }
  }, [legacyResults])

  useEffect(() => {
    localStorage.setItem('campaign_checker_mode', mode)
  }, [mode])

  useEffect(() => {
    localStorage.setItem('campaign_checker_api_port', apiPort)
  }, [apiPort])

  useEffect(() => {
    if (!loading) {
      progressStartRef.current = null
      setEtaSeconds(null)
      return
    }

    if (progressPct === 0) {
      progressStartRef.current = Date.now()
      setEtaSeconds(null)
      return
    }

    if (progressStartRef.current) {
      const elapsed = (Date.now() - progressStartRef.current) / 1000
      const remaining = progressPct > 0 ? Math.round((elapsed * (100 - progressPct)) / progressPct) : null
      setEtaSeconds(Number.isFinite(remaining) ? remaining : null)
    }
  }, [loading, progressPct])

  const handleNewCoverage = () => {
    setSiglipData(null)
    setLegacyResults([])
    setError(null)
    setExpandedCards({})
  }

  const getMediaUrl = (filepath) => {
    if (!filepath) return ''
    return `http://127.0.0.1:${apiPort}/media/?path=${encodeURIComponent(filepath)}`
  }

  const renderCardMedia = (filepath, filename) => {
    if (!filepath) return <i className="fa-solid fa-file file-type-icon"></i>
    const ext = filename ? filename.split('.').pop().toLowerCase() : filepath.split('.').pop().toLowerCase()
    const mediaUrl = getMediaUrl(filepath)
    
    if (['mp4', 'avi', 'mov', 'mkv', 'webm'].includes(ext)) {
      return (
        <div className="card-media-thumbnail-container video" onClick={(e) => e.stopPropagation()}>
          <video 
            className="card-media-thumbnail" 
            src={mediaUrl} 
            muted 
            loop 
            autoPlay 
            playsInline 
          />
          <div className="video-overlay-badge">
            <i className="fa-solid fa-play"></i>
          </div>
        </div>
      )
    }
    
    return (
      <div className="card-media-thumbnail-container image" onClick={(e) => e.stopPropagation()}>
        <img 
          className="card-media-thumbnail" 
          src={mediaUrl} 
          alt={filename || "thumbnail"} 
          onError={(e) => {
            e.target.style.display = 'none'
          }}
        />
      </div>
    )
  }

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
    const excelPath = siglipExcelPathRef.current ? siglipExcelPathRef.current.value.trim() : ''

    if (!refPath || (!targetPath && !excelPath)) {
      setError('من فضلك حط مجلد المراجع وكمان ملف هدف او ملف Excel.')
      return
    }

    setLoading(true)
    setError(null)
    setSiglipData(null)
    setExpandedCards({})
    setProgressLog([])
    setProgressPct(0)
    setProgressDetail('بنوصّل بمحرك المطابقة...')
    setProgressStep('init')

    try {
      const payload = {
        reference_path: refPath,
        campaign_name: campaignName,
        debug: siglipDebug
      }
      if (targetPath) payload.target_path = targetPath
      if (excelPath) {
        payload.excel_path = excelPath
      }

      const response = await fetch(`http://127.0.0.1:${apiPort}/campaign-match/`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload)
      })

      if (!response.ok) {
        throw new Error(`Server returned HTTP ${response.status}`)
      }

      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { value, done } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        
        // Save the last partial line back to the buffer
        buffer = lines.pop()

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const dataStr = line.slice(6).trim()
            if (!dataStr) continue

            try {
              const data = JSON.parse(dataStr)
              if (data.type === 'progress') {
                setProgressPct(data.pct || 0)
                setProgressDetail(data.detail || '')
                setProgressStep(data.step || '')
                setProgressLog(prev => {
                  // Avoid duplicate step logs if they are identical
                  if (prev.length > 0 && prev[prev.length - 1].detail === data.detail) {
                    return prev
                  }
                  const next = [...prev, {
                    timestamp: new Date().toLocaleTimeString(),
                    step: data.step,
                    detail: data.detail,
                    pct: data.pct
                  }]
                  return next.length > MAX_PROGRESS_LOG ? next.slice(-MAX_PROGRESS_LOG) : next
                })
              } else if (data.type === 'result') {
                setSiglipData(data)
                setProgressPct(100)
                setProgressDetail('التحليل خلص!')
                setProgressStep('complete')
              } else if (data.type === 'error') {
                setError(data.error)
              }
            } catch (e) {
              console.error('Error parsing SSE event:', e, dataStr)
            }
          }
        }
      }
    } catch (err) {
      setError('فشل الاتصال: ' + err.message)
    } finally {
      setLoading(false)
    }
  }

  const runLegacyAnalysis = async () => {
    const brand = legacyBrandRef.current ? legacyBrandRef.current.value.trim() : ''
    const targetPath = legacyTargetPathRef.current ? legacyTargetPathRef.current.value.trim() : ''
    const refPath = legacyRefPathRef.current ? legacyRefPathRef.current.value.trim() : ''
    const excelPath = legacyExcelPathRef.current ? legacyExcelPathRef.current.value.trim() : ''

    if (!brand) {
      setError('من فضلك اكتب اسم العلامة.')
      return
    }

    if (!refPath) {
      setError('من فضلك حط مسار شعارات المرجع.')
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
      if (excelPath) {
        payload.excel_path = excelPath
      }

      const res = await axios.post(`http://127.0.0.1:${apiPort}/run-analysis/`, payload)
      
      if (res.data.error) {
        setError(res.data.error)
      } else {
        const results = res.data.results || []
        setLegacyResults(results)
        if (results.length === 0) {
          setError('مفيش بوستات للتحليل. راجع المسارات.')
        }
      }
    } catch (err) {
      setError('فشل الاتصال: ' + (err.response?.data?.detail || err.message))
    } finally {
      setLoading(false)
    }
  }

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
      case 'VERIFIED_MATCH':
        return <span className="badge verified"><i className="fa-solid fa-circle-check"></i> مطابقة مؤكدة</span>
      case 'HIGH_CONFIDENCE_MATCH':
        return <span className="badge high"><i className="fa-solid fa-circle-check"></i> ثقة عالية</span>
      case 'REVIEW_REQUIRED':
        return <span className="badge review"><i className="fa-solid fa-eye"></i> محتاج مراجعة</span>
      case 'UNCERTAIN':
        return <span className="badge uncertain"><i className="fa-solid fa-circle-question"></i> غير واضح</span>
      case 'REJECTED':
        return <span className="badge rejected"><i className="fa-solid fa-circle-xmark"></i> مرفوض</span>
      case 'STRONG_MATCH':
        return <span className="badge strong"><i className="fa-solid fa-circle-check"></i> مطابقة قوية</span>
      case 'PROBABLE_STRONG_MATCH':
        return <span className="badge probable"><i className="fa-solid fa-circle-check"></i> غالبا مطابقة قوية</span>
      case 'POSSIBLE_MATCH':
        return <span className="badge possible"><i className="fa-solid fa-circle-question"></i> مطابقة محتملة</span>
      case 'NO_MATCH':
        return <span className="badge none"><i className="fa-solid fa-circle-xmark"></i> مش مطابق</span>
      default:
        return <span className="badge none"><i className="fa-solid fa-circle-xmark"></i> مش مطابق</span>
    }
  }

  const formatMatchLabel = (matchType) => {
    if (!matchType) return 'UNKNOWN'
    if (matchType === 'VERIFIED_MATCH') return 'مطابقة مؤكدة'
    if (matchType === 'HIGH_CONFIDENCE_MATCH') return 'مطابقة بثقة عالية'
    if (matchType === 'REVIEW_REQUIRED') return 'محتاج مراجعة'
    if (matchType === 'UNCERTAIN') return 'غير واضح'
    if (matchType === 'REJECTED') return 'مرفوض'
    if (matchType === 'STRONG_MATCH') return 'مطابقة قوية'
    if (matchType === 'PROBABLE_STRONG_MATCH') return 'غالبا مطابقة قوية'
    if (matchType === 'POSSIBLE_MATCH') return 'مطابقة محتملة'
    if (matchType === 'NO_MATCH') return 'مش مطابق'
    return matchType
  }

  const getScoreValue = (res) => {
    if (Number.isFinite(res?.score)) return res.score
    if (Number.isFinite(res?.confidence)) {
      return res.confidence > 1 ? res.confidence / 100 : res.confidence
    }
    if (Number.isFinite(res?.confidence_pct)) return res.confidence_pct / 100
    return 0
  }

  const getConfidencePct = (res) => {
    if (Number.isFinite(res?.confidence) && res.confidence > 1) {
      return Math.round(res.confidence)
    }
    if (Number.isFinite(res?.confidence_pct)) return Math.round(res.confidence_pct)
    const scoreValue = getScoreValue(res)
    return Math.round(scoreValue * 100)
  }

  const getPossibleThreshold = (res) => {
    if (Number.isFinite(res?.thresholds?.possible)) return res.thresholds.possible
    if (Number.isFinite(res?.threshold_used)) return res.threshold_used
    return null
  }

  // Get matching classification CSS state
  const getMatchClass = (matchType) => {
    if (matchType === 'VERIFIED_MATCH') return 'verified';
    if (matchType === 'HIGH_CONFIDENCE_MATCH') return 'high';
    if (matchType === 'REVIEW_REQUIRED') return 'review';
    if (matchType === 'UNCERTAIN') return 'uncertain';
    if (matchType === 'REJECTED') return 'rejected';
    if (matchType === 'STRONG_MATCH') return 'strong';
    if (matchType === 'PROBABLE_STRONG_MATCH') return 'probable';
    if (matchType === 'POSSIBLE_MATCH') return 'possible';
    if (matchType === 'NO_MATCH') return 'none';
    return 'none';
  }

  const resolveDecisionTier = (res) => res?.decision_tier || res?.match_type || 'UNKNOWN'

  const resolveFinalTier = (res) => {
    if (!res) return 'UNKNOWN'
    if (res.decision_tier) return res.decision_tier
    if (res.review_status === 'REJECTED') return 'NO_MATCH'
    if (res.review_status === 'REVIEW') return 'REVIEW_REQUIRED'
    if (res.review_status === 'APPROVED') {
      if (res.match_type === 'STRONG_MATCH') return 'VERIFIED_MATCH'
      if (res.match_type === 'POSSIBLE_MATCH') return 'HIGH_CONFIDENCE_MATCH'
    }
    return res.match_type || 'UNKNOWN'
  }

  const computeSummaryCounts = (data) => {
    const results = data?.results || []
    const tierCounts = data?.tier_counts || {}
    if (Object.keys(tierCounts).length > 0) {
      return {
        total: data?.summary?.num_targets ?? results.length,
        verified: tierCounts.VERIFIED_MATCH || 0,
        high: tierCounts.HIGH_CONFIDENCE_MATCH || 0,
        review: tierCounts.REVIEW_REQUIRED || 0,
        rejected: tierCounts.NO_MATCH || 0,
      }
    }

    const counts = { total: results.length, verified: 0, high: 0, review: 0, rejected: 0 }
    results.forEach((res) => {
      const tier = resolveFinalTier(res)
      if (tier === 'VERIFIED_MATCH') counts.verified += 1
      else if (tier === 'HIGH_CONFIDENCE_MATCH') counts.high += 1
      else if (tier === 'REVIEW_REQUIRED') counts.review += 1
      else if (tier === 'NO_MATCH') counts.rejected += 1
      else if (tier === 'STRONG_MATCH') counts.verified += 1
      else if (tier === 'POSSIBLE_MATCH') counts.review += 1
    })
    return counts
  }

  const boostReasonTranslations = {
    social_layout: 'تم رفع نسبة التطابق بسبب اكتشاف واجهة اجتماعية واضحة',
    platform_ui: 'تم رفع نسبة التطابق بسبب مؤشرات منصة قصيرة (تيك توك/ريلز/شورتس)',
    social_confidence: 'تم رفع نسبة التطابق بسبب ثقة عالية في تخطيط الوسائط الاجتماعية',
    logo_prominence: 'تم رفع نسبة التطابق بسبب ظهور شعار العلامة بوضوح وتمركز المنتج',
    brand_density: 'تم رفع نسبة التطابق بسبب هيمنة ألوان العلامة وتوافق المراجع',
    cluster_agreement: 'تم رفع نسبة التطابق بسبب توافق قوي مع عنقود المراجع',
  }

  const getBoostReasonText = (reason) => {
    if (!reason) return ''
    if (reason.code && boostReasonTranslations[reason.code]) return boostReasonTranslations[reason.code]
    return reason.detail || ''
  }

  const complianceStatusLabel = (status) => {
    if (status === 'PASS') return 'مطابق'
    if (status === 'FAIL') return 'غير مطابق'
    if (status === 'REVIEW') return 'مراجعة'
    if (status === 'NOT_PROVIDED') return 'مش متوفر'
    return status || 'غير معروف'
  }

  const formatComplianceIssue = (issue) => {
    if (!issue) return ''
    if (issue.startsWith('Missing hashtag:')) return `هاشتاج ناقص ${issue.split(': ').slice(1).join(': ')}`
    if (issue.startsWith('Missing mention:')) return `منشن ناقص ${issue.split(': ').slice(1).join(': ')}`
    if (issue.startsWith('Missing phrase:')) return `جملة ناقصة ${issue.split(': ').slice(1).join(': ')}`
    if (issue.startsWith('Forbidden term:')) return `كلمة ممنوعة ${issue.split(': ').slice(1).join(': ')}`
    if (issue.startsWith('Avoid promo phrase:')) return `بلاش جملة ترويجية ${issue.split(': ').slice(1).join(': ')}`
    if (issue.startsWith('Promo phrase detected:')) return `تم اكتشاف جملة ترويجية ${issue.split(': ').slice(1).join(': ')}`
    return issue
  }

  const openMediaReview = (res) => {
    if (!res) return
    const fallbackFrame = {
      frame_id: res.best_frame || res.filename || 'target',
      frame_path: res.file,
      score: res.score || 0,
      is_best: true,
      heatmap_path: res.heatmap_path || '',
    }

    const mediaItems = Array.isArray(res.frame_media) && res.frame_media.length > 0
      ? res.frame_media
      : [fallbackFrame]

    setReviewPayload({
      mediaItems,
      sourceFile: res.file,
      sourceFilename: res.filename,
      bestReferencePath: res.best_reference_path || '',
      bestReferenceName: res.best_reference || '',
      decisionTier: resolveDecisionTier(res),
      ocrDebug: res.ocr_debug || null,
      ocrOutput: res.ocr_output || null,
    })
    setReviewModalOpen(true)
  }

  const stagePipeline = [
    { key: 'LOADING_REFERENCES', labelAr: 'تحميل المراجع' },
    { key: 'EXTRACTING_FRAMES', labelAr: 'استخراج الفريمات' },
    { key: 'OCR_CAPTION', labelAr: 'تحليل الكابشن' },
    { key: 'HASHTAG_CHECK', labelAr: 'فحص الهاشتاجات' },
    { key: 'RULE_EVAL', labelAr: 'تقييم الالتزام' },
    { key: 'VISUAL_SIMILARITY', labelAr: 'تحليل التشابه' },
    { key: 'LOGO_ANALYSIS', labelAr: 'تحليل اللوجو' },
    { key: 'FINALIZING_RESULTS', labelAr: 'إنهاء النتائج' },
  ]

  const mapStepToStage = (step) => {
    if (step === 'INITIALIZING' || step === 'LOADING_REFERENCES') return 0
    if (step === 'EXTRACTING_FRAMES') return 1
    if (step === 'OCR_CAPTION') return 2
    if (step === 'HASHTAG_CHECK') return 3
    if (step === 'RULE_EVAL') return 4
    if (step === 'VISUAL_SIMILARITY') return 5
    if (step === 'LOGO_ANALYSIS') return 6
    if (step === 'FINALIZING_RESULTS' || step === 'complete') return 7
    return 0
  }

  const activeStageIndex = mapStepToStage(progressStep)

  const summaryCounts = computeSummaryCounts(siglipData)

  return (
    <div className="app-container">
      {/* Top Header */}
      <header>
        <div className="logo-section">
          <h1><i className="fa-solid fa-bolt-lightning"></i> فحص الحملة</h1>
          <p>منصة مطابقة بصرية ذكية وتحليل حملات السوشيال</p>
        </div>
        <div className="engine-badge">
          <span></span> محرك SigLIP v1.2 شغال
        </div>
      </header>

      {/* Main Grid: Control Panel (Left) & Results Display (Right) */}
      <main className="dashboard-grid">
        
        {/* Left Side: Parameters / Control Panel */}
        <section className="panel-card">
          <h2><i className="fa-solid fa-sliders"></i> لوحة التحكم</h2>

          {/* API Server Port Config */}
          <div className="form-group" style={{ marginBottom: '1.25rem' }}>
            <label>بورت السيرفر</label>
            <div className="input-wrapper">
              <input 
                type="text"
                className="form-control"
                placeholder="مثال: 8001"
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
              <i className="fa-solid fa-fingerprint"></i> مطابقة SigLIP
            </button>
            <button 
              className={`mode-btn ${mode === 'legacy' ? 'active' : ''}`}
              onClick={() => { setMode('legacy'); setError(null); }}
            >
              <i className="fa-solid fa-magnifying-glass"></i> التحليل القديم
            </button>
          </div>

          {/* Mode-specific forms */}
          {mode === 'siglip' ? (
            <div>
              <div className="form-group">
                <label>مجلد الصور المرجعية للحملة</label>
                <div className="input-wrapper">
                  <input 
                    ref={siglipRefPathRef}
                    className="form-control"
                    placeholder="مثال: data/reference"
                    defaultValue="data/reference"
                  />
                  <i className="fa-solid fa-folder-open"></i>
                </div>
              </div>

              <div className="form-group">
                <label>مسار الملف او المجلد الهدف (اختياري لو Excel)</label>
                <div className="input-wrapper">
                  <input 
                    ref={siglipTargetPathRef}
                    className="form-control"
                    placeholder="مثال: data/influencer_post.mp4"
                    defaultValue="data"
                  />
                  <i className="fa-solid fa-bullseye"></i>
                </div>
              </div>

              <div className="form-group">
                <label>مسار ملف Excel (اختياري)</label>
                <div className="input-wrapper">
                  <input 
                    ref={siglipExcelPathRef}
                    className="form-control"
                    placeholder="مثال: C:\\data\\posts.xlsx"
                    defaultValue=""
                  />
                  <i className="fa-solid fa-file-excel"></i>
                </div>
                <div className="form-hint">بيحدد اعمدة اليوزر واللينك تلقائي.</div>
              </div>

              <div className="form-group">
                <label>اسم الحملة</label>
                <div className="input-wrapper">
                  <input 
                    ref={siglipCampaignNameRef}
                    className="form-control"
                    placeholder="مثال: summer_promo_2026"
                    defaultValue="summer_promo"
                  />
                  <i className="fa-solid fa-tag"></i>
                </div>
              </div>

              <label className="checkbox-group">
                <input 
                  type="checkbox"
                  checked={siglipDebug}
                  onChange={(e) => setSiglipDebug(e.target.checked)}
                />
                <div className="custom-checkbox"></div>
                <span>تصدير ملفات الديباج للسيرفر</span>
              </label>

              <button 
                className="btn-primary" 
                onClick={runSiglipMatching}
                disabled={loading}
              >
                {loading ? (
                  <>
                    <i className="fa-solid fa-circle-notch fa-spin"></i> جاري التحليل...
                  </>
                ) : (
                  <>
                    <i className="fa-solid fa-wand-magic-sparkles"></i> تحقق من الحملة
                  </>
                )}
              </button>
            </div>
          ) : (
            <div>
              <div className="form-group">
                <label>اسم العلامة للبحث</label>
                <div className="input-wrapper">
                  <input 
                    ref={legacyBrandRef}
                    className="form-control"
                    placeholder="مثال: Nike, Coca-Cola"
                    defaultValue=""
                  />
                  <i className="fa-solid fa-copyright"></i>
                </div>
              </div>

              <div className="form-group">
                <label>مسار الملف او المجلد (اختياري)</label>
                <div className="input-wrapper">
                  <input 
                    ref={legacyTargetPathRef}
                    className="form-control"
                    placeholder="مثال: data"
                    defaultValue=""
                  />
                  <i className="fa-solid fa-file-invoice"></i>
                </div>
              </div>

              <div className="form-group">
                <label>مسار شعارات المرجع (اختياري)</label>
                <div className="input-wrapper">
                  <input 
                    ref={legacyRefPathRef}
                    className="form-control"
                    placeholder="مثال: data/logos"
                    defaultValue=""
                  />
                  <i className="fa-solid fa-images"></i>
                </div>
              </div>

              <div className="form-group">
                <label>مسار ملف Excel (اختياري)</label>
                <div className="input-wrapper">
                  <input 
                    ref={legacyExcelPathRef}
                    className="form-control"
                    placeholder="مثال: C:\\data\\posts.xlsx"
                    defaultValue=""
                  />
                  <i className="fa-solid fa-file-excel"></i>
                </div>
                <div className="form-hint">بيحدد اعمدة اليوزر واللينك تلقائي.</div>
              </div>

              <button 
                className="btn-primary" 
                onClick={runLegacyAnalysis}
                disabled={loading}
              >
                {loading ? (
                  <>
                    <i className="fa-solid fa-circle-notch fa-spin"></i> جاري فحص اللوجوهات...
                  </>
                ) : (
                  <>
                    <i className="fa-solid fa-search"></i> تشغيل تحليل اللوجوهات
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
          
          {/* State 1: Loading & Live Progress Panel */}
          {loading && (
            <div className="progress-panel">
              <div className="progress-panel-header">
                <div className="progress-status">
                  <div className="loading-spinner-small"></div>
                  <h3>خط التحقق شغال</h3>
                </div>
                <div className="progress-meta">
                  {etaSeconds !== null && (
                    <span className="progress-eta">الوقت المتبقي ~ {etaSeconds}ث</span>
                  )}
                  <span className="progress-pct-badge">{progressPct}%</span>
                </div>
              </div>

              {/* Progress Bar */}
              <div className="progress-bar-container">
                <div 
                  className="progress-bar-fill" 
                  style={{ width: `${progressPct}%` }}
                ></div>
              </div>

              <div className="progress-stage-list">
                {stagePipeline.map((stage, idx) => {
                  const state = idx < activeStageIndex ? 'complete' : idx === activeStageIndex ? 'active' : 'pending'
                  return (
                    <div key={stage.key} className={`progress-stage ${state}`}>
                      <div className="stage-dot"></div>
                      <div className="stage-label">
                        <span className="stage-ar">{stage.labelAr}</span>
                      </div>
                    </div>
                  )
                })}
              </div>

              {/* Current Active Step */}
              <div className="current-step-card">
                <div className="step-indicator pulse">
                  <i className="fa-solid fa-gear fa-spin"></i>
                </div>
                <div className="step-info">
                  <div className="step-title">المرحلة الحالية: <span className="mono">{progressStep.toUpperCase()}</span></div>
                  <p className="step-detail arabic">{stagePipeline[activeStageIndex]?.labelAr || progressDetail}</p>
                </div>
              </div>

              {/* Live Log Terminal */}
              <div className="log-terminal">
                <div className="log-terminal-header">
                  <div className="terminal-buttons">
                    <span className="btn-term red"></span>
                    <span className="btn-term yellow"></span>
                    <span className="btn-term green"></span>
                  </div>
                  <span className="terminal-title">سجل المتابعة</span>
                </div>
                <div className="log-terminal-body">
                  {progressLog.map((log, index) => (
                    <div key={index} className="log-line">
                      <span className="log-time">[{log.timestamp}]</span>
                      <span className="log-tag">[نظام]</span>
                      <span className="log-text">{log.detail}</span>
                      <span className="log-status-icon"><i className="fa-solid fa-check"></i></span>
                    </div>
                  ))}
                  {progressDetail && progressStep !== 'complete' && (
                    <div className="log-line active">
                      <span className="log-time">[{new Date().toLocaleTimeString()}]</span>
                      <span className="log-tag">[شغال]</span>
                      <span className="log-text">{progressDetail}...</span>
                      <span className="log-status-icon blinking">█</span>
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}

          {/* State 2: Welcome / Empty */}
          {!loading && !siglipData && legacyResults.length === 0 && (
            <div className="empty-state">
              <i className="fa-solid fa-robot empty-state-icon"></i>
              <h3>جاهزين للتحقق</h3>
              <p>حدد صور الحملة والميديا المطلوبة من لوحة التحكم وبعدها شغل التحقق عشان تستلم تقرير واضح.</p>
            </div>
          )}

          {/* State 3: SigLIP Results Display */}
          {!loading && siglipData && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
              
              {/* Summary Metrics Card */}
              <div className="summary-card">
                <div className="summary-header">
                  <div className="summary-title">
                    <h3>تقرير مطابقة الحملة</h3>
                    <span>{siglipData.summary?.campaign_name || 'تحقق'}</span>
                  </div>
                  <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'center' }}>
                    <div className="engine-badge" style={{ borderColor: 'var(--accent-muted)' }}>
                      {siglipData.summary?.num_references} مرجع متحمل
                    </div>
                    <button className="btn-secondary" onClick={handleNewCoverage}>
                      <i className="fa-solid fa-rotate-left"></i> تقرير جديد
                    </button>
                  </div>
                </div>

                <div className="summary-stats">
                  <div className="stat-item">
                    <div className="stat-val accent">{summaryCounts.total}</div>
                    <div className="stat-label">إجمالي العناصر</div>
                  </div>
                  <div className="stat-item">
                    <div className="stat-val strong">{summaryCounts.verified}</div>
                    <div className="stat-label">مطابقة مؤكدة</div>
                  </div>
                  <div className="stat-item">
                    <div className="stat-val high">{summaryCounts.high}</div>
                    <div className="stat-label">ثقة عالية</div>
                  </div>
                  <div className="stat-item">
                    <div className="stat-val review">{summaryCounts.review}</div>
                    <div className="stat-label">محتاج مراجعة</div>
                  </div>
                  <div className="stat-item">
                    <div className="stat-val none">{summaryCounts.rejected}</div>
                    <div className="stat-label">مرفوض</div>
                  </div>
                </div>

                <div className="info-row">
                  <i className="fa-solid fa-circle-info"></i>
                  <span>تباين المراجع: <strong>{siglipData.summary?.reference_variance}</strong>. كل ما الرقم يقل كل ما المراجع متقاربة.</span>
                </div>
              </div>

              {/* Reference Set Quality Card */}
              {siglipData.summary?.cohesion_metrics && (
                <div className="cohesion-panel">
                  <div className="cohesion-header">
                    <div className="cohesion-title"><i className="fa-solid fa-gem"></i> جودة المراجع</div>
                    <span className={`cohesion-quality-badge ${siglipData.summary.cohesion_metrics.cluster_quality?.toLowerCase()}`}>
                      {siglipData.summary.cohesion_metrics.cluster_quality}
                    </span>
                  </div>
                  <div className="cohesion-bar-wrapper">
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
                      <span>Silhouette Cohesion Score</span>
                      <span className="mono">{Math.round(siglipData.summary.cohesion_metrics.silhouette_score * 100)}%</span>
                    </div>
                    <div className="cohesion-bar-track">
                      <div className="cohesion-bar-fill" style={{ width: `${Math.round(siglipData.summary.cohesion_metrics.silhouette_score * 100)}%` }}></div>
                    </div>
                  </div>
                  <div className="calibration-grid" style={{ gridTemplateColumns: '1fr 1fr', marginTop: '0.5rem', borderTop: 'none', paddingTop: '0' }}>
                    <div className="calibration-stat-row" style={{ borderBottom: 'none' }}>
                      <span className="calibration-stat-label" style={{ fontSize: '0.75rem' }}>Intra Similarity Mean</span>
                      <span className="calibration-stat-val" style={{ fontSize: '0.75rem' }}>{siglipData.summary.cohesion_metrics.intra_similarity_mean?.toFixed(4)}</span>
                    </div>
                    <div className="calibration-stat-row" style={{ borderBottom: 'none' }}>
                      <span className="calibration-stat-label" style={{ fontSize: '0.75rem' }}>Intra Similarity Std</span>
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
                      <h3><i className="fa-solid fa-share-nodes" style={{ color: 'var(--accent-light)' }}></i> Social UI Analytics</h3>
                      <span>Distribution Telemetry</span>
                    </div>
                    <div className="engine-badge" style={{ borderColor: 'var(--accent-muted)', color: 'var(--match-probable)' }}>
                      <i className="fa-solid fa-chart-pie"></i> {Math.round(siglipData.social_analytics.social_ratio * 100)}% Social Ratio
                    </div>
                  </div>

                  <div className="summary-stats" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(110px, 1fr))', gap: '0.75rem' }}>
                    <div className="stat-item">
                      <div className="stat-val" style={{ color: 'var(--accent-light)', fontSize: '1.35rem' }}>
                        {Math.round(siglipData.social_analytics.social_ratio * 100)}%
                      </div>
                      <div className="stat-label" style={{ fontSize: '0.65rem' }}>Social Media</div>
                    </div>
                    <div className="stat-item">
                      <div className="stat-val" style={{ color: 'var(--match-possible)', fontSize: '1.35rem' }}>
                        {Math.round(siglipData.social_analytics.vertical_ratio * 100)}%
                      </div>
                      <div className="stat-label" style={{ fontSize: '0.65rem' }}>Vertical Format</div>
                    </div>
                    <div className="stat-item">
                      <div className="stat-val" style={{ color: 'var(--match-none)', fontSize: '1.35rem' }}>
                        {Math.round(siglipData.social_analytics.overlay_ratio * 100)}%
                      </div>
                      <div className="stat-label" style={{ fontSize: '0.65rem' }}>UI / Overlays</div>
                    </div>
                    <div className="stat-item">
                      <div className="stat-val" style={{ color: 'var(--text-secondary)', fontSize: '1.35rem' }}>
                        {Math.round(siglipData.social_analytics.mobile_screenshot_ratio * 100)}%
                      </div>
                      <div className="stat-label" style={{ fontSize: '0.65rem' }}>Screenshots</div>
                    </div>
                    <div className="stat-item">
                      <div className="stat-val" style={{ color: 'var(--match-strong)', fontSize: '1.35rem' }}>
                        +{siglipData.social_analytics.average_social_adjustment?.toFixed(3)}
                      </div>
                      <div className="stat-label" style={{ fontSize: '0.65rem' }}>Avg UI Boost</div>
                    </div>
                  </div>

                  {siglipData.social_analytics.platform_distribution && Object.keys(siglipData.social_analytics.platform_distribution).length > 0 && (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', borderTop: '1px dashed var(--border-color)', paddingTop: '0.75rem' }}>
                      <div style={{ fontSize: '0.75rem', fontWeight: '700', textTransform: 'uppercase', color: 'var(--text-muted)', letterSpacing: '0.05em' }}>
                        المنصات المكتشفة
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
                              <i className={platformIcon}></i> {platformLabel}: {count} {count === 1 ? 'بوست' : 'بوستات'}
                            </span>
                          );
                        })}
                      </div>
                    </div>
                  )}
                </div>
              )}

              {/* Individual Target Cards list */}
              <div className="results-header">قائمة التحقق</div>
              <div className="results-list">
                {siglipData.results?.map((res, index) => {
                  const isExpanded = !!expandedCards[index]
                  const decisionLabel = resolveDecisionTier(res)
                  const verdictClass = getMatchClass(decisionLabel)
                  const confidencePct = getConfidencePct(res)
                  const scoreValue = getScoreValue(res)
                  const possibleThreshold = getPossibleThreshold(res)
                  const decisionMargin = Number.isFinite(possibleThreshold) ? (scoreValue - possibleThreshold) : null
                  const competitorMargin = Number.isFinite(res.competitor_margin) ? res.competitor_margin : null
                  const competitorRisk = (
                    (Number.isFinite(res.competitor_similarity) && res.competitor_similarity >= 0.72) ||
                    (Number.isFinite(competitorMargin) && competitorMargin <= 0.08)
                  )
                  
                  return (
                    <div className={`result-card ${verdictClass}`} key={index}>
                      <div className="result-main" onClick={() => toggleExpandCard(index)}>
                        <div className="result-meta">
                          <div className="file-info">
                            {renderCardMedia(res.file, res.filename)}
                            <div style={{ display: 'flex', flexDirection: 'column', minWidth: 0, flexGrow: 1 }}>
                              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap' }}>
                                <span className="file-name" title={res.filename}>{res.filename || 'محتوى الهدف'}</span>
                                {renderVerdictBadge(decisionLabel)}
                                {res.error && (
                                  <span className="badge rejected" title={res.error}>
                                    <i className="fa-solid fa-triangle-exclamation"></i> فشل التحميل
                                  </span>
                                )}
                                <button 
                                  className="copy-path-badge-btn" 
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    navigator.clipboard.writeText(res.file);
                                    const target = e.currentTarget;
                                    const icon = target.querySelector('i');
                                    icon.className = 'fa-solid fa-check';
                                    target.classList.add('copied');
                                    setTimeout(() => {
                                      icon.className = 'fa-solid fa-copy';
                                      target.classList.remove('copied');
                                    }, 1500);
                                  }}
                                  title="نسخ مسار الملف"
                                >
                                  <i className="fa-solid fa-copy"></i>
                                </button>
                                {res.source_url && (
                                  <a
                                    className="copy-path-badge-btn"
                                    href={res.source_url}
                                    target="_blank"
                                    rel="noreferrer"
                                    onClick={(e) => e.stopPropagation()}
                                    title="فتح رابط المصدر"
                                  >
                                    <i className="fa-solid fa-link"></i>
                                  </a>
                                )}
                              </div>
                              {res.media_context && (
                                <div className="media-badges-row">
                                  <span className="media-badge">
                                    <i className="fa-solid fa-expand"></i> النسبة: {res.media_context.aspect_ratio?.toFixed(2)}
                                  </span>
                                  {res.media_context.is_social_media && (
                                    <span className="media-badge highlight">
                                      <i className="fa-solid fa-share-nodes"></i> شكل سوشيال
                                    </span>
                                  )}
                                  {res.media_context.has_overlays && (
                                    <span className="media-badge warning">
                                      <i className="fa-solid fa-rectangle-ad"></i> اوفرلاي
                                    </span>
                                  )}
                                  {res.media_context.compression_level > 0.4 && (
                                    <span className="media-badge">
                                      <i className="fa-solid fa-compress"></i> ضغط: {Math.round(res.media_context.compression_level * 100)}%
                                    </span>
                                  )}
                                  {res.media_context.suggested_threshold_offset < 0 && (
                                    <span className="media-badge highlight">
                                      <i className="fa-solid fa-sliders"></i> تعويض: {res.media_context.suggested_threshold_offset?.toFixed(2)}
                                    </span>
                                  )}
                                  {res.platform && res.platform !== 'unknown' && (
                                    <span className="media-badge highlight">
                                      <i className="fa-solid fa-hashtag"></i> {res.platform.replace('_', ' ').toUpperCase()}
                                    </span>
                                  )}
                                </div>
                              )}
                            </div>
                          </div>
                        </div>

                        <div className="score-section">
                          <div className="gauge-wrapper">
                            <span className={`gauge-pct ${getMatchClass(decisionLabel)}`}>
                              {confidencePct}%
                            </span>
                            <div className="gauge-track">
                              <div 
                                className={`gauge-fill ${getMatchClass(decisionLabel)}`}
                                style={{ width: `${confidencePct}%` }}
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
                          {/* Visual Asset Inspection Showcase */}
                          <div className="expanded-media-showcase">
                            <div className="detail-section-title">
                              <i className="fa-solid fa-eye"></i> مراجعة الميديا
                            </div>
                            <div className="media-review-actions">
                              <button className="btn-secondary" onClick={(e) => { e.stopPropagation(); openMediaReview(res); }}>
                                <i className="fa-solid fa-magnifying-glass"></i> افتح مراجعة الميديا
                              </button>
                            </div>
                            <div className="expanded-media-viewer">
                              {(() => {
                                const ext = res.filename ? res.filename.split('.').pop().toLowerCase() : res.file.split('.').pop().toLowerCase()
                                const mediaUrl = getMediaUrl(res.file)
                                if (['mp4', 'avi', 'mov', 'mkv', 'webm'].includes(ext)) {
                                  return (
                                    <video 
                                      className="expanded-media-player" 
                                      src={mediaUrl} 
                                      controls 
                                      playsInline 
                                    />
                                  )
                                }
                                return (
                                  <img 
                                    className="expanded-media-image" 
                                    src={mediaUrl} 
                                    alt={res.filename || "visual asset"} 
                                  />
                                )
                              })()}
                            </div>
                          </div>

                          {/* Top Row: Metrics & References */}
                          <div className="detail-row">
                            {/* Similarity Metrics */}
                            <div>
                              <div className="detail-section-title">
                                <i className="fa-solid fa-chart-line"></i> مؤشرات التشابه
                              </div>
                              <div className="matching-highlights">
                                <div className="highlight-box">
                                  <span className="highlight-label">نتيجة المطابقة</span>
                                  <span className="highlight-val">{formatMatchLabel(decisionLabel)}</span>
                                </div>
                                <div className="highlight-box">
                                  <span className="highlight-label">السكور المدمج</span>
                                  <span className="highlight-val mono">{scoreValue.toFixed(4)}</span>
                                </div>
                                <div className="highlight-box">
                                  <span className="highlight-label">أعلى تشابه</span>
                                  <span className="highlight-val mono">{(res.top_similarity).toFixed(4)}</span>
                                </div>
                                <div className="highlight-box">
                                  <span className="highlight-label">متوسط التشابه</span>
                                  <span className="highlight-val mono">{(res.average_similarity).toFixed(4)}</span>
                                </div>
                                <div className="highlight-box">
                                  <span className="highlight-label">العتبة المستخدمة</span>
                                  <span className="highlight-val mono">{possibleThreshold !== null ? possibleThreshold.toFixed(4) : 'N/A'}</span>
                                </div>
                                <div className="highlight-box">
                                  <span className="highlight-label">عدد الفريمات</span>
                                  <span className="highlight-val">{res.num_frames_analyzed}</span>
                                </div>
                                {res.best_reference && (
                                  <div className="highlight-box">
                                    <span className="highlight-label">أفضل مرجع</span>
                                    <span className="highlight-val" style={{ maxWidth: '180px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={res.best_reference}>
                                      {res.best_reference}
                                    </span>
                                  </div>
                                )}
                                <div className="highlight-box">
                                  <span className="highlight-label">وقت المعالجة</span>
                                  <span className="highlight-val">{res.processing_time_ms} ms</span>
                                </div>
                                <div className="highlight-box">
                                  <span className="highlight-label">حالة المراجعة</span>
                                  <span className="highlight-val">{res.review_status || 'N/A'}</span>
                                </div>
                                {res.error && (
                                  <div className="highlight-box">
                                    <span className="highlight-label">خطأ التحميل</span>
                                    <span className="highlight-val" title={res.error}>{res.error}</span>
                                  </div>
                                )}
                                {res.decision_tier && (
                                  <div className="highlight-box">
                                    <span className="highlight-label">تصنيف القرار</span>
                                    <span className="highlight-val">{formatMatchLabel(res.decision_tier)}</span>
                                  </div>
                                )}
                              </div>
                            </div>

                            {/* Reference Matching Breakdown */}
                            <div>
                              <div className="detail-section-title">
                                <i className="fa-solid fa-cubes"></i> تفاصيل المراجع
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

                            {/* Caption OCR & Compliance */}
                            {(res.ocr_output || res.compliance_report || res.caption_compliance) && (
                              <div className="detail-row">
                                <div>
                                  <div className="detail-section-title">
                                    <i className="fa-solid fa-file-signature"></i> تحليل الكابشن والالتزام
                                  </div>
                                  <div className="matching-highlights">
                                    <div className="highlight-box">
                                      <span className="highlight-label">حالة الالتزام</span>
                                      <span className="highlight-val">
                                        {complianceStatusLabel(res.compliance_report?.status || res.caption_compliance)}
                                      </span>
                                    </div>
                                    {Number.isFinite(res.compliance_report?.compliance_score) && (
                                      <div className="highlight-box">
                                        <span className="highlight-label">درجة الالتزام</span>
                                        <span className="highlight-val">{res.compliance_report.compliance_score}%</span>
                                      </div>
                                    )}
                                    {res.ocr_output?.platform && (
                                      <div className="highlight-box">
                                        <span className="highlight-label">المنصة</span>
                                        <span className="highlight-val">{res.ocr_output.platform}</span>
                                      </div>
                                    )}
                                  </div>

                                  {res.ocr_output?.caption && (
                                    <div className="caption-preview">
                                      <div className="caption-label">الكابشن المستخرج</div>
                                      <div className="caption-text">{res.ocr_output.caption}</div>
                                    </div>
                                  )}

                                  {(res.ocr_output?.hashtags?.length > 0 || res.ocr_output?.mentions?.length > 0) && (
                                    <div className="caption-tags">
                                      {res.ocr_output?.hashtags?.length > 0 && (
                                        <div className="caption-tag-row">هاشتاجات: {res.ocr_output.hashtags.join(' ')}</div>
                                      )}
                                      {res.ocr_output?.mentions?.length > 0 && (
                                        <div className="caption-tag-row">منشنز: {res.ocr_output.mentions.join(' ')}</div>
                                      )}
                                    </div>
                                  )}

                                  {((res.compliance_report?.violations || []).length > 0 || (res.compliance_report?.missing_rules || []).length > 0) && (
                                    <div className="caption-issues">
                                      {[...(res.compliance_report?.violations || []), ...(res.compliance_report?.missing_rules || [])].map((issue, iIdx) => (
                                        <div key={iIdx} className="caption-issue">
                                          <i className="fa-solid fa-triangle-exclamation"></i>
                                          <span>{formatComplianceIssue(issue)}</span>
                                        </div>
                                      ))}
                                    </div>
                                  )}
                                </div>
                              </div>
                            )}

                          {/* Row 2: Brand Overlap & Ambiguity Gauges */}
                          <div className="detail-row">
                            {/* Competitor Overlap Gauges */}
                            <div>
                              <div className="detail-section-title">
                                <i className="fa-solid fa-shield-halved"></i> تداخل المنافسين
                              </div>
                              <div className="matching-highlights">
                                <div className="highlight-box-vertical">
                                  <div className="highlight-vertical-header">
                                    <span className="highlight-label">قرب المنافس</span>
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
                                      أقرب منافس: <strong>{res.explainability.best_competitor}</strong>
                                    </div>
                                  )}
                                </div>

                                <div className="highlight-box-vertical">
                                  <div className="highlight-vertical-header">
                                    <span className="highlight-label">غموض القرار</span>
                                    <span className="highlight-val mono">{(res.ambiguity_score || 0.0).toFixed(4)}</span>
                                  </div>
                                  <div className="competitor-track">
                                    <div 
                                      className={`competitor-fill ${res.ambiguity_score > 0.60 ? 'danger' : res.ambiguity_score > 0.30 ? 'warning' : 'safe'}`}
                                      style={{ width: `${(res.ambiguity_score || 0.0) * 100}%` }}
                                    ></div>
                                  </div>
                                  <div className="competitor-meta-info">
                                    الحالة: <strong className={competitorRisk ? 'txt-danger' : 'txt-safe'}>{competitorRisk ? 'محتاج مراجعة' : 'هامش آمن'}</strong>
                                  </div>
                                </div>
                              </div>
                            </div>

                            {/* Diagnostics Panel & Warnings */}
                            <div>
                              <div className="detail-section-title">
                                <i className="fa-solid fa-stethoscope"></i> سجل التشخيص والتفسير
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
                                    <strong>كل المؤشرات تمام:</strong> مفيش تداخل منافسين واضح.
                                  </div>
                                </div>
                              )}

                              {res.explainability?.boost_reasons && res.explainability.boost_reasons.length > 0 && (
                                <div className="boost-reasons">
                                  <div className="boost-reasons-title">أسباب رفع الثقة</div>
                                  {res.explainability.boost_reasons.map((reason, rIdx) => (
                                    <div key={rIdx} className="boost-reason-item">
                                      <i className="fa-solid fa-sparkles"></i>
                                      <span>{getBoostReasonText(reason)}</span>
                                    </div>
                                  ))}
                                </div>
                              )}
                            </div>
                          </div>

                          {/* Platt Calibration / Temporal Stability Grid */}
                          <div className="calibration-grid">
                            {/* Calibration Card 1: Platt scaling */}
                            <div className="calibration-card">
                              <div className="calibration-card-header">
                                <i className="fa-solid fa-chart-line"></i> معايرة الثقة
                              </div>
                              <div className="calibration-stat-row">
                                <span className="calibration-stat-label">الثقة بعد المعايرة</span>
                                <span className={`calibration-stat-val ${res.match_type === 'STRONG_MATCH' ? 'highlight-green' : res.match_type === 'PROBABLE_STRONG_MATCH' ? 'highlight-gold' : ''}`}>
                                  {confidencePct}%
                                </span>
                              </div>
                              <div className="calibration-stat-row">
                                <span className="calibration-stat-label">أعلى تشابه خام</span>
                                <span className="calibration-stat-val">{res.top_similarity?.toFixed(4)}</span>
                              </div>
                              <div className="calibration-stat-row">
                                <span className="calibration-stat-label">متوسط تشابه خام</span>
                                <span className="calibration-stat-val">{res.average_similarity?.toFixed(4)}</span>
                              </div>
                              <div className="calibration-stat-row">
                                <span className="calibration-stat-label">العتبة الحالية</span>
                                <span className="calibration-stat-val">{possibleThreshold !== null ? possibleThreshold.toFixed(4) : 'N/A'}</span>
                              </div>
                              <div className="calibration-stat-row">
                                <span className="calibration-stat-label">هامش القرار</span>
                                <span className="calibration-stat-val">{decisionMargin !== null ? decisionMargin.toFixed(4) : 'N/A'}</span>
                              </div>
                            </div>

                            {/* Calibration Card 2: Temporal Stability */}
                            <div className="calibration-card">
                              <div className="calibration-card-header">
                                <i className="fa-solid fa-clock-rotate-left"></i> ثبات الفيديو
                              </div>
                              <div className="calibration-stat-row">
                                <span className="calibration-stat-label">قوة الاستمرارية</span>
                                <span className="calibration-stat-val highlight-green">{Number.isFinite(res.temporal_strength) ? res.temporal_strength.toFixed(4) : 'N/A'}</span>
                              </div>
                              <div className="calibration-stat-row">
                                <span className="calibration-stat-label">عدد الفريمات</span>
                                <span className="calibration-stat-val">{res.num_frames_analyzed}</span>
                              </div>
                              <div className="calibration-stat-row">
                                <span className="calibration-stat-label">عدد المقاطع الثابتة</span>
                                <span className="calibration-stat-val">{res.stable_segments ? res.stable_segments.length : 0}</span>
                              </div>
                              <div className="calibration-stat-row">
                                <span className="calibration-stat-label">أفضل فريم</span>
                                <span className="calibration-stat-val" style={{ maxWidth: '160px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={res.best_frame}>
                                  {res.best_frame || 'N/A'}
                                </span>
                              </div>
                              <div className="calibration-stat-row">
                                <span className="calibration-stat-label">حالة التشخيص</span>
                                <span className="calibration-stat-val">{res.warnings && res.warnings.length > 0 ? 'تحذيرات' : 'تمام'}</span>
                              </div>
                            </div>

                            {/* Calibration Card 3: Reference Cluster & Boost Telemetry */}
                            <div className="calibration-card">
                              <div className="calibration-card-header">
                                <i className="fa-solid fa-cubes"></i> مجموعات المراجع والضبط
                              </div>
                              <div className="calibration-stat-row">
                                <span className="calibration-stat-label">المجموعة الأساسية</span>
                                <span className="calibration-stat-val" style={{ color: 'var(--accent-light)' }}>
                                  {(() => {
                                    const cl = res.dominant_cluster;
                                    if (cl === 'logo_refs') return 'مراجع لوجو';
                                    if (cl === 'drink_refs') return 'مراجع مشروب';
                                    if (cl === 'product_refs') return 'مراجع منتج';
                                    if (cl === 'store_refs') return 'مراجع المتجر';
                                    return cl || 'مركز عام';
                                  })()}
                                </span>
                              </div>
                              <div className="calibration-stat-row">
                                <span className="calibration-stat-label">تشابه المركز</span>
                                <span className="calibration-stat-val">
                                  {res.cluster_similarity !== undefined && res.cluster_similarity !== null ? res.cluster_similarity.toFixed(4) : '0.0000'}
                                </span>
                              </div>
                              <div className="calibration-stat-row">
                                <span className="calibration-stat-label">تعديل واجهة السوشيال</span>
                                <span className={`calibration-stat-val ${res.social_adjustment > 0 ? 'highlight-green' : ''}`}>
                                  {res.social_adjustment > 0 ? `+${res.social_adjustment.toFixed(3)}` : '0.000'}
                                </span>
                              </div>
                              <div className="calibration-stat-row">
                                <span className="calibration-stat-label">تعزيز المنتج</span>
                                <span className={`calibration-stat-val ${res.product_boost > 0 ? 'highlight-green' : ''}`}>
                                  {res.product_boost > 0 ? `+${res.product_boost.toFixed(3)}` : '0.000'}
                                </span>
                              </div>
                              <div className="calibration-stat-row">
                                <span className="calibration-stat-label">تعزيز بصري</span>
                                <span className={`calibration-stat-val ${res.visual_boost > 0 ? 'highlight-green' : ''}`}>
                                  {res.visual_boost > 0 ? `+${res.visual_boost.toFixed(3)}` : '0.000'}
                                </span>
                              </div>
                              <div className="calibration-stat-row">
                                <span className="calibration-stat-label">حالة التعزيز</span>
                                <span className="calibration-stat-val">
                                  {res.social_adjustment > 0 || res.product_boost > 0 || res.visual_boost > 0 ? 'تعزيز شغال' : 'طبيعي'}
                                </span>
                              </div>
                            </div>

                            {/* Calibration Card 4: Visual signals */}
                            {res.visual_signal && (
                              <div className="calibration-card">
                                <div className="calibration-card-header">
                                  <i className="fa-solid fa-eye"></i> تحليل الإشارات البصرية
                                </div>
                                <div className="calibration-stat-row">
                                  <span className="calibration-stat-label">قوة اللوجو</span>
                                  <span className="calibration-stat-val">{Math.round((res.visual_signal.logo_strength || 0) * 100)}%</span>
                                </div>
                                <div className="calibration-stat-row">
                                  <span className="calibration-stat-label">تركيز المنتج</span>
                                  <span className="calibration-stat-val">{Math.round((res.visual_signal.product_focus || 0) * 100)}%</span>
                                </div>
                                <div className="calibration-stat-row">
                                  <span className="calibration-stat-label">كثافة العلامة</span>
                                  <span className="calibration-stat-val">{Math.round((res.visual_signal.branding_density || 0) * 100)}%</span>
                                </div>
                                <div className="calibration-stat-row">
                                  <span className="calibration-stat-label">ثقة واجهة السوشيال</span>
                                  <span className="calibration-stat-val">{Math.round((res.visual_signal.social_media_confidence || 0) * 100)}%</span>
                                </div>
                              </div>
                            )}
                          </div>

                          {/* Model Decision Reasoning Chain */}
                          {res.explainability?.reasoning_steps && (
                            <div>
                              <div className="detail-section-title">
                                <i className="fa-solid fa-brain"></i> تسلسل قرار النموذج
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
                                  const title = parts.length > 1 && parts[0].length < 30 ? parts[0] : `Step ${sIdx + 1}`;
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
                                <i className="fa-solid fa-chart-area"></i> خط زمني للتطابق
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
                                  {Number.isFinite(possibleThreshold) && (() => {
                                    const yThresh = 120 - (possibleThreshold * 100);
                                    return (
                                      <g>
                                        <line x1="50" y1={yThresh} x2="750" y2={yThresh} stroke="var(--match-possible)" strokeWidth="1.5" strokeDasharray="3,3" />
                                        <text x="755" y={yThresh + 3} fill="var(--match-possible)" fontSize="9" fontWeight="bold">THR: {possibleThreshold.toFixed(2)}</text>
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
                                      const score = frame.score !== undefined ? frame.score : (frame.smoothed_similarity !== undefined ? frame.smoothed_similarity : frame.max_similarity);
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
                                    const smVal = frame.score !== undefined ? frame.score : (frame.smoothed_similarity !== undefined ? frame.smoothed_similarity : frame.max_similarity);
                                    const ySmooth = 120 - (smVal * 100);
                                    const isMatched = Number.isFinite(possibleThreshold) ? smVal >= possibleThreshold : false;
                                    
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
                                        <title>{`Frame: ${frame.frame_id}\nRaw Score: ${(frame.raw_score !== undefined ? frame.raw_score : frame.max_similarity).toFixed(3)}\nSmoothed: ${smVal.toFixed(3)}\nCompetitor Proximity: ${(frame.competitor_similarity !== undefined ? frame.competitor_similarity : 0.0).toFixed(3)}\nBest Reference: ${frame.best_reference}`}</title>
                                      </g>
                                    )
                                  })}
                                </svg>
                              </div>
                              
                              {/* Dynamic Legend */}
                              <div className="timeline-legend">
                                <div className="legend-item"><span className="legend-dot raw"></span> سكور خام</div>
                                <div className="legend-item"><span className="legend-dot smoothed"></span> سكور سلس</div>
                                <div className="legend-item"><span className="legend-dot competitor"></span> قرب المنافس</div>
                                <div className="legend-item"><span className="legend-dot thresh"></span> عتبة المطابقة</div>
                              </div>

                              {/* Active Matching Timeline Segment Pills */}
                              {res.stable_segments && res.stable_segments.length > 0 && (
                                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem', marginTop: '0.75rem', justifyContent: 'center' }}>
                                  {res.stable_segments.map((seg, sIdx) => (
                                    <span key={sIdx} className="media-badge highlight" style={{ fontSize: '0.8rem', padding: '0.35rem 0.65rem' }}>
                                      <i className="fa-solid fa-circle-play"></i> مقطع {sIdx + 1}: فريمات {seg.start_frame}-{seg.end_frame} ({seg.duration_frames}) | متوسط: {(seg.average_score * 100).toFixed(1)}%
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
                                <i className="fa-solid fa-photo-film"></i> تحليل الفريمات
                              </div>
                              <div className="keyframes-grid">
                                {res.frame_scores.map((frame, fIndex) => (
                                  <div className="keyframe-card" key={fIndex}>
                                    <div className="keyframe-id" title={frame.frame_id}>{frame.frame_id}</div>
                                    <div className="keyframe-score">{(frame.max_similarity * 100).toFixed(1)}%</div>
                                    <div className="keyframe-ref" title={frame.best_reference}>مرجع: {frame.best_reference}</div>
                                  </div>
                                ))}
                              </div>
                            </div>
                          )}
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
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div className="results-header" style={{ marginTop: 0 }}>نتائج التحليل القديم</div>
                <button className="btn-secondary" onClick={handleNewCoverage}>
                  <i className="fa-solid fa-rotate-left"></i> تقرير جديد
                </button>
              </div>
              <div className="results-list">
                {legacyResults.map((r, i) => (
                  <div className="result-card STRONG_MATCH" key={i} style={{ borderLeft: '4px solid var(--accent)' }}>
                    <div className="result-main" style={{ cursor: 'default' }}>
                      <div className="result-meta">
                        <div className="file-info">
                          {renderCardMedia(r.file, r.file.split(/[\\/]/).pop())}
                          <div style={{ display: 'flex', flexDirection: 'column', minWidth: 0, flexGrow: 1 }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap' }}>
                              <span className="file-name" style={{ maxWidth: '350px' }}>{r.file.split(/[\\/]/).pop()}</span>
                              <span className="badge legacy">{r.influencer || 'بوست'} ({r.platform || 'منصة'})</span>
                              <button 
                                className="copy-path-badge-btn" 
                                onClick={(e) => {
                                  e.stopPropagation();
                                  navigator.clipboard.writeText(r.file);
                                  const target = e.currentTarget;
                                  const icon = target.querySelector('i');
                                  icon.className = 'fa-solid fa-check';
                                  target.classList.add('copied');
                                  setTimeout(() => {
                                    icon.className = 'fa-solid fa-copy';
                                    target.classList.remove('copied');
                                  }, 1500);
                                }}
                                title="نسخ مسار الملف"
                              >
                                <i className="fa-solid fa-copy"></i>
                              </button>
                              {r.source_url && (
                                <a
                                  className="copy-path-badge-btn"
                                  href={r.source_url}
                                  target="_blank"
                                  rel="noreferrer"
                                  onClick={(e) => e.stopPropagation()}
                                  title="فتح رابط المصدر"
                                >
                                  <i className="fa-solid fa-link"></i>
                                </a>
                              )}
                            </div>
                          </div>
                        </div>
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

      <MediaReviewModal
        open={reviewModalOpen}
        onClose={() => setReviewModalOpen(false)}
        mediaItems={reviewPayload?.mediaItems || []}
        sourceFile={reviewPayload?.sourceFile || ''}
        sourceFilename={reviewPayload?.sourceFilename || ''}
        bestReferencePath={reviewPayload?.bestReferencePath || ''}
        bestReferenceName={reviewPayload?.bestReferenceName || ''}
        decisionTier={reviewPayload?.decisionTier || ''}
        ocrDebug={reviewPayload?.ocrDebug || null}
        ocrOutput={reviewPayload?.ocrOutput || null}
        getMediaUrl={getMediaUrl}
      />
    </div>
  )
}
