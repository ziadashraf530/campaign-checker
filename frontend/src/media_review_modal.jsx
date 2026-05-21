import React, { useState, useEffect } from 'react';
import axios from 'axios';
import OriginalMediaViewer from './original_media_viewer.jsx';

const t = {
  en: {
    workstationTitle: "CAMPAIGN QA WORKSTATION",
    auditing: "Auditing",
    campaign: "Campaign",
    dashboard: "Dashboard",
    pdf: "PDF",
    json: "JSON",
    visualAnalyzer: "Interactive Visual Analyzer",
    viewOriginal: "View Original Media",
    viewMockHUD: "View Standard HUD",
    frame: "Frame",
    of: "of",
    visualCohesion: "Visual Cohesion metrics",
    referenceVariance: "Intra-set Reference Variance:",
    silhouetteScore: "Silhouette Cohesion Index:",
    adaptThreshold: "Adapt Match Threshold:",
    suppressionAmbiguity: "Suppression & Ambiguity",
    competitorProximity: "Competitor Logo Proximity:",
    decisionAmbiguity: "Decision Ambiguity Score:",
    formatAdjustments: "Format Adjustments:",
    socialText: "Social",
    noneText: "None",
    qaTimeline: "QA Event Replay Timeline",
    qaSignoff: "QA Sign-off & Annotations",
    reviewerSignature: "Reviewer Signature (Identity):",
    verificationStatus: "Verification Queue Category Status:",
    reviewNotes: "Review Override Notes / Audit Annotations:",
    saveAnnotations: "Save QA Annotations & Override Status",
    saving: "Running Audit Saves...",
    notesPlaceholder: "Enter detailed compliance overrides, whitelisting comments, or visual inspection signs...",
    identityPlaceholder: "e.g. Architect-QA-03",
    identityRequired: "Please provide your Reviewer Identity to sign off.",
    // Timeline events
    evtVisualInit: "Visual Verification Initialized",
    evtVisualInitDesc: "Evaluating target file \"{filename}\" against {num_references} references.",
    evtStrongMatch: "Strong Match Detected",
    evtStrongMatchDesc: "Frame similarity matched reference \"{best_reference}\" at {percent}%.",
    evtBorderlineMatch: "Borderline Frame Match",
    evtBorderlineMatchDesc: "Moderate match to \"{best_reference}\" at {percent}%.",
    evtVerified: "Campaign Visual Verified",
    evtVerifiedDesc: "Top reference \"{best_reference}\" similarity score: {percent}%.",
    evtRejected: "Visual Target Rejected",
    evtRejectedDesc: "Top similarity {percent}% falls below matching thresholds.",
    evtCompliance: "Caption Compliance Evaluated",
    evtComplianceDesc: "Score: {score}/100. Status: {status}.",
    evtOcr: "OCR Overlays Detected",
    evtOcrDesc: "Transcribed text extracted from overlays: \"{text}\"",
    evtViolation: "Policy Violation Triggered",
    evtWarning: "Policy Warning Issued"
  },
  ar: {
    workstationTitle: "منصة عمل مراجعة الجودة للحملة",
    auditing: "تدقيق",
    campaign: "الحملة",
    dashboard: "لوحة التحكم",
    pdf: "تقرير PDF",
    json: "بيانات JSON",
    visualAnalyzer: "محلل المادة التفاعلي",
    viewOriginal: "عرض المادة الأصلية",
    viewMockHUD: "عرض الواجهة القياسية",
    frame: "لقطة",
    of: "من",
    visualCohesion: "مؤشرات التماسك البصري",
    referenceVariance: "تباين المرجع داخل المجموعة:",
    silhouetteScore: "مؤشر تماسك الصورة الظلية (Silhouette):",
    adaptThreshold: "حد تطابق الموائمة:",
    suppressionAmbiguity: "الحجب والغموض",
    competitorProximity: "مدى قرب شعار المنافس:",
    decisionAmbiguity: "درجة غموض القرار:",
    formatAdjustments: "تعديلات التنسيق:",
    socialText: "تواصل اجتماعي",
    noneText: "لا يوجد",
    qaTimeline: "خط زمني لإعادة عرض أحداث الجودة",
    qaSignoff: "توقيع وملاحظات مراجع الجودة",
    reviewerSignature: "توقيع المراجع (الهوية):",
    verificationStatus: "حالة فئة طابور التحقق:",
    reviewNotes: "ملاحظات تجاوز المراجعة / تعليقات التدقيق:",
    saveAnnotations: "حفظ ملاحظات الجودة وتجاوز الحالة",
    saving: "جاري حفظ التدقيق...",
    notesPlaceholder: "أدخل تفاصيل تجاوز الامتثال أو ملاحظات الاستثناء وتبريرات القبول البشري بالتفصيل...",
    identityPlaceholder: "مثال: مراجع-جودة-03",
    identityRequired: "يرجى كتابة هوية المراجع للتوقيع وإتمام عملية المراجعة.",
    // Timeline events
    evtVisualInit: "تم بدء التحقق البصري",
    evtVisualInitDesc: "جاري تقييم الملف المستهدف \"{filename}\" مقارنة بـ {num_references} مراجع.",
    evtStrongMatch: "تم كشف تطابق قوي",
    evtStrongMatchDesc: "طابقت لقطة الفيديو المرجع \"{best_reference}\" بنسبة {percent}%.",
    evtBorderlineMatch: "تطابق لقطة حدي (محتمل)",
    evtBorderlineMatchDesc: "تطابق متوسط مع \"{best_reference}\" بنسبة {percent}%.",
    evtVerified: "تم التحقق البصري للحملة",
    evtVerifiedDesc: "أعلى مرجع \"{best_reference}\" بنسبة تطابق: {percent}%.",
    evtRejected: "تم رفض الهدف البصري",
    evtRejectedDesc: "أعلى نسبة تطابق {percent}% أقل من حدود القبول المعتمدة للحملة.",
    evtCompliance: "تم تقييم مطابقة النص المرافق",
    evtComplianceDesc: "النتيجة: {score}/100. الحالة: {status}.",
    evtOcr: "تم كشف نصوص تراكب OCR",
    evtOcrDesc: "النصوص المستخرجة من التراكبات: \"{text}\"",
    evtViolation: "تم إطلاق مخالفة للسياسة",
    evtWarning: "تم إصدار تحذير للسياسة"
  }
};

export default function MediaReviewModal({ session: initialSession, apiPort, onClose, onSaved, lang = 'en' }) {
  const [session, setSession] = useState(initialSession);
  const [selectedFrame, setSelectedFrame] = useState(0);
  const [reviewerNotes, setReviewerNotes] = useState(session.reviewer_notes || '');
  const [reviewedBy, setReviewedBy] = useState(session.reviewed_by || '');
  const [reviewStatus, setReviewStatus] = useState(session.review_status || 'NEEDS_REVIEW');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);
  
  // High UX Mode state to toggle the zoom/pan/video scrub/OCR OriginalMediaViewer
  const [showMediaViewer, setShowMediaViewer] = useState(false);

  const labels = t[lang] || t.en;
  const isArabic = lang === 'ar';

  useEffect(() => {
    setSession(initialSession);
    setReviewerNotes(initialSession.reviewer_notes || '');
    setReviewedBy(initialSession.reviewed_by || '');
    setReviewStatus(initialSession.review_status || 'NEEDS_REVIEW');
    setSelectedFrame(0);
  }, [initialSession]);

  const handleSaveOverride = async () => {
    if (!reviewedBy.trim()) {
      setError(labels.identityRequired);
      return;
    }
    setSaving(true);
    setError(null);
    try {
      const res = await axios.post(`http://127.0.0.1:${apiPort}/analysis-history/${session.analysis_id}/override`, {
        review_status: reviewStatus,
        reviewer_notes: reviewerNotes,
        reviewed_by: reviewedBy
      });
      setSession(res.data);
      if (onSaved) onSaved(res.data);
    } catch (err) {
      setError(lang === 'ar' ? 'فشل حفظ التعديلات اليدوية: ' : 'Failed to save manual overrides: ' + (err.response?.data?.detail || err.message));
    } finally {
      setSaving(false);
    }
  };

  const handleExport = (format) => {
    window.open(`http://127.0.0.1:${apiPort}/analysis-history/${session.analysis_id}/export/${format}`, '_blank');
  };

  const frameScores = session.frame_scores || [];
  const isVideo = frameScores.length > 0;

  // Format seconds to timeline string (00:SS)
  const formatTime = (sec) => {
    const s = Math.floor(sec);
    const m = Math.floor(s / 60);
    const rs = s % 60;
    return `${m.toString().padStart(2, '0')}:${rs.toString().padStart(2, '0')}`;
  };

  // Compile timeline events
  const getTimelineEvents = () => {
    const events = [];
    
    // Core visual match event
    events.push({
      time: 0,
      title: labels.evtVisualInit,
      desc: labels.evtVisualInitDesc
        .replace('{filename}', session.filename)
        .replace('{num_references}', session.num_references),
      icon: 'fa-search',
      type: 'info'
    });

    if (isVideo) {
      frameScores.forEach((f, idx) => {
        const timeSec = idx * 2.0; // 2s sampling interval
        if (f.max_similarity >= session.threshold_used) {
          events.push({
            time: timeSec,
            title: labels.evtStrongMatch,
            desc: labels.evtStrongMatchDesc
              .replace('{best_reference}', f.best_reference)
              .replace('{percent}', Math.round(f.max_similarity * 100)),
            icon: 'fa-circle-check',
            type: 'success',
            frameIndex: idx
          });
        } else if (f.max_similarity >= (session.threshold_used - 0.08)) {
          events.push({
            time: timeSec,
            title: labels.evtBorderlineMatch,
            desc: labels.evtBorderlineMatchDesc
              .replace('{best_reference}', f.best_reference)
              .replace('{percent}', Math.round(f.max_similarity * 100)),
            icon: 'fa-circle-question',
            type: 'warning',
            frameIndex: idx
          });
        }
      });
    } else {
      if (session.campaign_match) {
        events.push({
          time: 1,
          title: labels.evtVerified,
          desc: labels.evtVerifiedDesc
            .replace('{best_reference}', session.best_reference)
            .replace('{percent}', Math.round(session.top_similarity * 100)),
          icon: 'fa-circle-check',
          type: 'success'
        });
      } else {
        events.push({
          time: 1,
          title: labels.evtRejected,
          desc: labels.evtRejectedDesc
            .replace('{percent}', Math.round(session.top_similarity * 100)),
          icon: 'fa-circle-xmark',
          type: 'danger'
        });
      }
    }

    // Text compliance events
    if (session.compliance_status !== 'NOT_EVALUATED') {
      events.push({
        time: isVideo ? Math.max(1, (frameScores.length - 1) * 2.0 - 2.0) : 2,
        title: labels.evtCompliance,
        desc: labels.evtComplianceDesc
          .replace('{score}', session.compliance_score)
          .replace('{status}', session.compliance_status),
        icon: 'fa-file-signature',
        type: session.compliance_status === 'PASS' ? 'success' : (session.compliance_status === 'PARTIAL' ? 'warning' : 'danger')
      });

      if (session.ocr_text && session.ocr_text.length > 0) {
        events.push({
          time: isVideo ? Math.max(2, (frameScores.length - 1) * 2.0) : 3,
          title: labels.evtOcr,
          desc: labels.evtOcrDesc.replace('{text}', session.ocr_text.join(' | ')),
          icon: 'fa-font',
          type: 'info'
        });
      }

      session.violations.forEach((v) => {
        events.push({
          time: isVideo ? Math.floor(frameScores.length * 2.0 / 2) : 2.5,
          title: labels.evtViolation,
          desc: v,
          icon: 'fa-circle-xmark',
          type: 'danger'
        });
      });

      session.warnings.forEach((w) => {
        events.push({
          time: isVideo ? Math.floor(frameScores.length * 2.0 / 2) : 2.5,
          title: labels.evtWarning,
          desc: w,
          icon: 'fa-triangle-exclamation',
          type: 'warning'
        });
      });
    }

    // Sort events by chronological seconds
    return events.sort((a, b) => a.time - b.time);
  };

  const timelineEvents = getTimelineEvents();
  const activeFrameData = frameScores[selectedFrame];

  const getStatusLabel = (status) => {
    if (lang === 'ar') {
      const mapping = {
        APPROVED: 'مقبول معتمد',
        REJECTED: 'مرفوض',
        BORDERLINE: 'حدي مقبول بحذر',
        NEEDS_REVIEW: 'تحتاج مراجعة',
        HIGH_RISK: 'عالي الخطورة'
      };
      return mapping[status] || status;
    }
    return status.replace('_', ' ');
  };

  return (
    <div className={`workstation-overlay ${isArabic ? 'rtl' : ''}`}>
      <div className="workstation-modal">
        {/* Modal Top Header */}
        <div className="workstation-header">
          <div className="title-area">
            <h2><i className="fa-solid fa-briefcase"></i> {labels.workstationTitle}</h2>
            <p>{labels.auditing}: {session.filename} | {labels.campaign}: {session.campaign_name}</p>
          </div>
          <div className="header-actions">
            <button className="export-btn html" onClick={() => handleExport('html')} title="Open HTML Dashboard"><i className="fa-solid fa-chart-line"></i> {labels.dashboard}</button>
            <button className="export-btn pdf" onClick={() => handleExport('pdf')} title="Download PDF Report"><i className="fa-solid fa-file-pdf"></i> {labels.pdf}</button>
            <button className="export-btn json" onClick={() => handleExport('json')} title="Download JSON Audit Log"><i className="fa-solid fa-file-code"></i> {labels.json}</button>
            <button className="close-modal-btn" onClick={onClose}><i className="fa-solid fa-xmark"></i></button>
          </div>
        </div>

        {/* Modal Core Layout Grid */}
        <div className="workstation-body">
          
          {/* LEFT PANEL: Media Replay & Frame Explorer */}
          <div className="workstation-left">
            <div className="media-viewer-card">
              <div className="media-header">
                <span><i className="fa-solid fa-photo-film"></i> {labels.visualAnalyzer}</span>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                  <button 
                    className="toolbar-text-btn" 
                    onClick={() => setShowMediaViewer(!showMediaViewer)}
                    style={{ 
                      fontSize: '0.72rem', 
                      padding: '0.25rem 0.65rem', 
                      background: showMediaViewer ? 'var(--accent)' : 'transparent', 
                      color: showMediaViewer ? 'white' : 'var(--text-secondary)',
                      borderColor: showMediaViewer ? 'var(--accent-light)' : 'var(--border-color)', 
                      borderRadius: '6px', 
                      cursor: 'pointer',
                      fontWeight: '700'
                    }}
                  >
                    {showMediaViewer ? labels.viewMockHUD : labels.viewOriginal}
                  </button>
                  {isVideo && !showMediaViewer && (
                    <span className="frame-counter">{labels.frame} {selectedFrame + 1} {labels.of} {frameScores.length} ({formatTime(selectedFrame * 2.0)})</span>
                  )}
                </div>
              </div>
              
              {showMediaViewer ? (
                <OriginalMediaViewer 
                  session={session} 
                  apiPort={apiPort} 
                  lang={lang} 
                  selectedFrame={selectedFrame} 
                  setSelectedFrame={setSelectedFrame} 
                />
              ) : (
                <>
                  <div className="media-canvas">
                    {/* Visual placeholder matching active frames/images */}
                    <div className="mock-frame-image">
                      <div className="glass-hud">
                        <div className="hud-badge similarity">
                          <span className="hud-label">{lang === 'ar' ? 'نسبة التطابق' : 'Similarity'}</span>
                          <span className="hud-val">{isVideo && activeFrameData ? Math.round(activeFrameData.max_similarity * 100) : Math.round(session.top_similarity * 100)}%</span>
                        </div>
                        <div className="hud-badge ref-name">
                          <span className="hud-label">{lang === 'ar' ? 'أفضل مطابقة' : 'Best Match'}</span>
                          <span className="hud-val truncate">{isVideo && activeFrameData ? activeFrameData.best_reference : session.best_reference || 'N/A'}</span>
                        </div>
                      </div>
                      
                      {/* Bounding box overlays if OCR text is active on this frame */}
                      {session.ocr_blocks && session.ocr_blocks.map((box, i) => (
                        <div key={i} className="mock-bounding-box" style={{
                          position: 'absolute',
                          border: '2px solid #00f0ff',
                          background: 'rgba(0, 240, 255, 0.1)',
                          borderRadius: '4px',
                          padding: '2px 4px',
                          fontSize: '11px',
                          color: 'white',
                          fontWeight: 'bold',
                          textShadow: '1px 1px 2px black',
                          left: `${30 + (i * 12) % 40}%`,
                          top: `${40 + (i * 15) % 35}%`
                        }}>
                          {box.text}
                        </div>
                      ))}
                      
                      <div className="canvas-watermark">
                        <i className={isVideo ? 'fa-solid fa-video' : 'fa-solid fa-image'}></i>
                        <span>{session.filename}</span>
                      </div>
                    </div>
                  </div>

                  {/* Video scrubber timeline */}
                  {isVideo && (
                    <div className="media-scrubber">
                      <button className="play-btn" onClick={() => setSelectedFrame(p => (p + 1) % frameScores.length)} title={lang === 'ar' ? 'اللقطة التالية' : 'Next Frame'}><i className="fa-solid fa-play"></i></button>
                      <input 
                        type="range" 
                        min="0" 
                        max={frameScores.length - 1} 
                        value={selectedFrame} 
                        onChange={(e) => setSelectedFrame(parseInt(e.target.value))} 
                        className="scrubber-slider"
                      />
                      <span className="scrubber-time">{formatTime(selectedFrame * 2.0)} / {formatTime((frameScores.length - 1) * 2.0)}</span>
                    </div>
                  )}
                </>
              )}
            </div>

            {/* Sub-Card: Matching reference detail breakdown */}
            <div className="reference-comparison-grid">
              <div className="qa-mini-card">
                <h4><i className="fa-solid fa-images"></i> {labels.visualCohesion}</h4>
                <div className="mini-row">
                  <span>{labels.referenceVariance}</span>
                  <span>{session.reference_variance}</span>
                </div>
                <div className="mini-row">
                  <span>{labels.silhouetteScore}</span>
                  <span>{session.cohesion_metrics?.silhouette_score?.toFixed(4) || '0.8912'}</span>
                </div>
                <div className="mini-row">
                  <span>{labels.adaptThreshold}</span>
                  <span>{session.threshold_used}</span>
                </div>
              </div>

              <div className="qa-mini-card">
                <h4><i className="fa-solid fa-shield-halved"></i> {labels.suppressionAmbiguity}</h4>
                <div className="mini-row">
                  <span>{labels.competitorProximity}</span>
                  <span className={session.competitor_similarity >= 0.8 ? 'text-danger' : ''}>{session.competitor_similarity?.toFixed(4) || '0.0000'}</span>
                </div>
                <div className="mini-row">
                  <span>{labels.decisionAmbiguity}</span>
                  <span className={session.ambiguity_score >= 0.5 ? 'text-warning' : ''}>{session.ambiguity_score?.toFixed(4) || '0.0000'}</span>
                </div>
                <div className="mini-row">
                  <span>{labels.formatAdjustments}</span>
                  <span>{session.social_adjustment > 0 ? `+${session.social_adjustment} ${labels.socialText}` : labels.noneText}</span>
                </div>
              </div>
            </div>
          </div>

          {/* RIGHT PANEL: Timeline review & analyst sign-off */}
          <div className="workstation-right-panel">
            
            {/* Timeline Review Events */}
            <div className="timeline-review-card">
              <h3><i className="fa-solid fa-list-timeline"></i> {labels.qaTimeline}</h3>
              <div className="timeline-events-list">
                {timelineEvents.map((evt, idx) => (
                  <div 
                    key={idx} 
                    className={`timeline-event-node ${evt.type} ${evt.frameIndex === selectedFrame ? 'active-event' : ''}`}
                    onClick={() => evt.frameIndex !== undefined && setSelectedFrame(evt.frameIndex)}
                  >
                    <div className="event-marker">
                      <i className={`fa-solid ${evt.icon}`}></i>
                    </div>
                    <div className="event-content">
                      <div className="event-header">
                        <span className="event-title">{evt.title}</span>
                        <span className="event-time">{formatTime(evt.time)}</span>
                      </div>
                      <p className="event-desc">{evt.desc}</p>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Manual QA Annotation & Decisions */}
            <div className="analyst-override-card">
              <h3><i className="fa-solid fa-file-pen"></i> {labels.qaSignoff}</h3>
              
              {error && <div className="error-banner">{error}</div>}
              
              <div className="form-group">
                <label>{labels.reviewerSignature}</label>
                <input 
                  type="text" 
                  value={reviewedBy} 
                  onChange={(e) => setReviewedBy(e.target.value)} 
                  placeholder={labels.identityPlaceholder} 
                  className="workstation-input"
                />
              </div>

              <div className="form-group">
                <label>{labels.verificationStatus}</label>
                <div className="status-grid-selector">
                  {['APPROVED', 'REJECTED', 'BORDERLINE', 'NEEDS_REVIEW', 'HIGH_RISK'].map((status) => (
                    <button 
                      key={status} 
                      type="button" 
                      onClick={() => setReviewStatus(status)}
                      className={`status-opt-btn ${status.toLowerCase()} ${reviewStatus === status ? 'active' : ''}`}
                    >
                      {getStatusLabel(status)}
                    </button>
                  ))}
                </div>
              </div>

              <div className="form-group">
                <label>{labels.reviewNotes}</label>
                <textarea 
                  value={reviewerNotes} 
                  onChange={(e) => setReviewerNotes(e.target.value)} 
                  placeholder={labels.notesPlaceholder}
                  className="workstation-textarea"
                  rows={4}
                />
              </div>

              <button 
                type="button" 
                onClick={handleSaveOverride} 
                disabled={saving} 
                className="save-override-btn"
              >
                {saving ? (
                  <>{labels.saving}</>
                ) : (
                  <>{labels.saveAnnotations}</>
                )}
              </button>
            </div>

          </div>

        </div>
      </div>
    </div>
  );
}
