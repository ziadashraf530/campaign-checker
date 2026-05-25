import { useEffect, useMemo, useState } from 'react'

export default function MediaReviewModal({
  open,
  onClose,
  mediaItems,
  sourceFile,
  sourceFilename,
  bestReferencePath,
  bestReferenceName,
  decisionTier,
  ocrDebug,
  ocrOutput,
  getMediaUrl,
}) {
  const [activeIndex, setActiveIndex] = useState(0)
  const [zoom, setZoom] = useState(1)
  const [showHeatmap, setShowHeatmap] = useState(true)
  const [viewMode, setViewMode] = useState('frame')
  const [showOcrRegions, setShowOcrRegions] = useState(true)
  const [showOcrIgnored, setShowOcrIgnored] = useState(false)
  const [showOcrText, setShowOcrText] = useState(true)
  const [showHashtags, setShowHashtags] = useState(true)
  const [showMentions, setShowMentions] = useState(true)
  const [showCaptionText, setShowCaptionText] = useState(true)

  const isVideo = useMemo(() => {
    if (!sourceFilename) return false
    const ext = sourceFilename.split('.').pop().toLowerCase()
    return ['mp4', 'avi', 'mov', 'mkv', 'webm'].includes(ext)
  }, [sourceFilename])

  useEffect(() => {
    if (!open) return
    const bestIdx = mediaItems.findIndex(item => item.is_best)
    setActiveIndex(bestIdx >= 0 ? bestIdx : 0)
    setZoom(1)
    setShowHeatmap(true)
    setViewMode('frame')
    setShowOcrRegions(true)
    setShowOcrIgnored(false)
    setShowOcrText(true)
    setShowHashtags(true)
    setShowMentions(true)
    setShowCaptionText(true)
  }, [open, mediaItems])

  if (!open) return null

  const activeItem = mediaItems[activeIndex] || mediaItems[0]
  const heatmapUrl = activeItem?.heatmap_path ? getMediaUrl(activeItem.heatmap_path) : ''
  const frameUrl = activeItem?.frame_path ? getMediaUrl(activeItem.frame_path) : ''
  const referenceUrl = bestReferencePath ? getMediaUrl(bestReferencePath) : ''
  const ocrRegions = ocrDebug?.regions || []
  const ocrIgnored = ocrDebug?.ignored_regions || []
  const ocrDetections = Array.isArray(ocrDebug?.detections) ? ocrDebug.detections : []
  const ocrFrameMatch = ocrDebug?.frame_id ? ocrDebug.frame_id === activeItem?.frame_id : true

  const tierLabel = (() => {
    if (decisionTier === 'VERIFIED_MATCH') return 'مطابقة مؤكدة'
    if (decisionTier === 'HIGH_CONFIDENCE_MATCH') return 'ثقة عالية'
    if (decisionTier === 'REVIEW_REQUIRED') return 'محتاج مراجعة'
    if (decisionTier === 'NO_MATCH') return 'مش مطابق'
    if (decisionTier === 'REJECTED') return 'مرفوض'
    return decisionTier ? decisionTier.replace('_', ' ') : ''
  })()

  return (
    <div className="media-modal-backdrop" onClick={onClose}>
      <div className="media-modal" onClick={(e) => e.stopPropagation()}>
        <div className="media-modal-header">
          <div>
            <div className="media-modal-title">مراجعة الميديا</div>
            {decisionTier && <div className="media-modal-tier">{tierLabel}</div>}
          </div>
          <button className="media-modal-close" onClick={onClose}>
            <i className="fa-solid fa-xmark"></i>
          </button>
        </div>

        <div className="media-modal-body">
          <div className="media-modal-viewer">
            <div className="media-modal-toolbar">
              {isVideo && (
                <div className="media-modal-toggle">
                  <button
                    className={`toggle-btn ${viewMode === 'frame' ? 'active' : ''}`}
                    onClick={() => setViewMode('frame')}
                  >
                    فريمات
                  </button>
                  <button
                    className={`toggle-btn ${viewMode === 'video' ? 'active' : ''}`}
                    onClick={() => setViewMode('video')}
                  >
                    فيديو
                  </button>
                </div>
              )}
              <div className="media-modal-zoom">
                <button className="zoom-btn" onClick={() => setZoom(Math.max(0.6, zoom - 0.1))}>-</button>
                <span className="zoom-val">{Math.round(zoom * 100)}%</span>
                <button className="zoom-btn" onClick={() => setZoom(Math.min(2.5, zoom + 0.1))}>+</button>
              </div>
              {heatmapUrl && viewMode === 'frame' && (
                <label className="heatmap-toggle">
                  <input
                    type="checkbox"
                    checked={showHeatmap}
                    onChange={(e) => setShowHeatmap(e.target.checked)}
                  />
                  <span>هيتماب</span>
                </label>
              )}
              {viewMode === 'frame' && ocrDebug && (
                <div className="ocr-toggle-group">
                  <label className="heatmap-toggle">
                    <input
                      type="checkbox"
                      checked={showOcrRegions}
                      onChange={(e) => setShowOcrRegions(e.target.checked)}
                    />
                    <span>مناطق الكابشن</span>
                  </label>
                  <label className="heatmap-toggle">
                    <input
                      type="checkbox"
                      checked={showOcrIgnored}
                      onChange={(e) => setShowOcrIgnored(e.target.checked)}
                    />
                    <span>واجهة متجاهلة</span>
                  </label>
                  <label className="heatmap-toggle">
                    <input
                      type="checkbox"
                      checked={showOcrText}
                      onChange={(e) => setShowOcrText(e.target.checked)}
                    />
                    <span>النص المكتشف</span>
                  </label>
                  <label className="heatmap-toggle">
                    <input
                      type="checkbox"
                      checked={showCaptionText}
                      onChange={(e) => setShowCaptionText(e.target.checked)}
                    />
                    <span>كابشن</span>
                  </label>
                  <label className="heatmap-toggle">
                    <input
                      type="checkbox"
                      checked={showHashtags}
                      onChange={(e) => setShowHashtags(e.target.checked)}
                    />
                    <span>هاشتاج</span>
                  </label>
                  <label className="heatmap-toggle">
                    <input
                      type="checkbox"
                      checked={showMentions}
                      onChange={(e) => setShowMentions(e.target.checked)}
                    />
                    <span>منشن</span>
                  </label>
                </div>
              )}
            </div>

            <div className="media-modal-stage">
              {viewMode === 'video' && isVideo ? (
                <video className="media-modal-video" src={getMediaUrl(sourceFile)} controls playsInline />
              ) : (
                <div className="media-modal-frame-wrapper">
                  {frameUrl && (
                    <img
                      className="media-modal-frame"
                      src={frameUrl}
                      alt={activeItem?.frame_id || 'frame'}
                      style={{ transform: `scale(${zoom})` }}
                    />
                  )}
                  {heatmapUrl && showHeatmap && (
                    <img
                      className="media-modal-heatmap"
                      src={heatmapUrl}
                      alt="heatmap"
                      style={{ transform: `scale(${zoom})` }}
                    />
                  )}
                  {ocrDebug && ocrFrameMatch && viewMode === 'frame' && (
                    <div className="ocr-overlay-layer" style={{ transform: `scale(${zoom})` }}>
                      {showOcrRegions && ocrRegions.map((region, idx) => (
                        <div
                          key={`ocr-region-${idx}`}
                          className="ocr-box ocr-region"
                          style={{
                            left: `${region.box[0] * 100}%`,
                            top: `${region.box[1] * 100}%`,
                            width: `${(region.box[2] - region.box[0]) * 100}%`,
                            height: `${(region.box[3] - region.box[1]) * 100}%`,
                          }}
                          title={region.label}
                        />
                      ))}
                      {showOcrIgnored && ocrIgnored.map((region, idx) => (
                        <div
                          key={`ocr-ignore-${idx}`}
                          className="ocr-box ocr-ignore"
                          style={{
                            left: `${region.box[0] * 100}%`,
                            top: `${region.box[1] * 100}%`,
                            width: `${(region.box[2] - region.box[0]) * 100}%`,
                            height: `${(region.box[3] - region.box[1]) * 100}%`,
                          }}
                          title={region.label}
                        />
                      ))}
                      {showOcrText && ocrDetections.map((det, idx) => {
                        const categories = det.categories || []
                        if (categories.includes('hashtag') && !showHashtags) return null
                        if (categories.includes('mention') && !showMentions) return null
                        if (categories.includes('caption') && !showCaptionText) return null
                        const classNames = ['ocr-box', 'ocr-detect']
                        if (categories.includes('hashtag')) classNames.push('ocr-hashtag')
                        if (categories.includes('mention')) classNames.push('ocr-mention')
                        if (categories.includes('caption')) classNames.push('ocr-caption')
                        return (
                          <div
                            key={`ocr-det-${idx}`}
                            className={classNames.join(' ')}
                            style={{
                              left: `${det.box[0] * 100}%`,
                              top: `${det.box[1] * 100}%`,
                              width: `${(det.box[2] - det.box[0]) * 100}%`,
                              height: `${(det.box[3] - det.box[1]) * 100}%`,
                            }}
                            title={det.text}
                          />
                        )
                      })}
                    </div>
                  )}
                  {ocrDebug && !ocrFrameMatch && viewMode === 'frame' && (
                    <div className="ocr-overlay-note">الـ OCR متاح على أفضل فريم بس</div>
                  )}
                </div>
              )}
            </div>
          </div>

          <div className="media-modal-sidebar">
            {referenceUrl && (
              <div className="reference-preview">
                <div className="sidebar-title">أقوى مرجع</div>
                <img src={referenceUrl} alt={bestReferenceName || 'reference'} />
                {bestReferenceName && <div className="reference-name" title={bestReferenceName}>{bestReferenceName}</div>}
              </div>
            )}

            {ocrOutput && (
              <div className="reference-preview">
                <div className="sidebar-title">ملخص الكابشن</div>
                <div className="ocr-summary">
                  <div className="ocr-summary-line">{ocrOutput.caption || 'مفيش كابشن واضح'}</div>
                  {ocrOutput.hashtags?.length > 0 && (
                    <div className="ocr-summary-tags">{ocrOutput.hashtags.join(' ')}</div>
                  )}
                  {ocrOutput.mentions?.length > 0 && (
                    <div className="ocr-summary-mentions">{ocrOutput.mentions.join(' ')}</div>
                  )}
                </div>
              </div>
            )}

            <div className="keyframe-panel">
              <div className="sidebar-title">الفريمات المهمة</div>
              <div className="keyframe-list">
                {mediaItems.map((item, idx) => (
                  <button
                    key={`${item.frame_id}-${idx}`}
                    className={`keyframe-thumb ${idx === activeIndex ? 'active' : ''}`}
                    onClick={() => setActiveIndex(idx)}
                    title={item.frame_id}
                  >
                    <img src={getMediaUrl(item.frame_path)} alt={item.frame_id} />
                    <span>{Math.round((item.score || 0) * 100)}%</span>
                  </button>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
