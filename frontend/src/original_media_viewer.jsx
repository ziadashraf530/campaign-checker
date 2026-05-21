import React, { useState, useEffect, useRef } from 'react';

const t = {
  en: {
    zoomIn: "Zoom In",
    zoomOut: "Zoom Out",
    reset: "Reset",
    pan: "Drag to Pan",
    viewVideo: "Original Video",
    viewKeyframes: "Frame Explorer",
    hideOverlays: "Hide Overlays",
    showBoxes: "OCR Outlines",
    showIgnored: "Show Ignored UI",
    showFiltered: "Compliant Only",
    ocrOverlay: "OCR Overlay",
    confidence: "Confidence",
    ignoredUI: "Ignored UI Element",
    compliantText: "Compliant Text",
    mediaError: "Media could not be loaded",
    currentFrame: "Active Frame",
    atTime: "at"
  },
  ar: {
    zoomIn: "تكبير",
    zoomOut: "تصغير",
    reset: "إعادة ضبط",
    pan: "اسحب للتحريك",
    viewVideo: "الفيديو الأصلي",
    viewKeyframes: "مستكشف اللقطات",
    hideOverlays: "إخفاء التراكبات",
    showBoxes: "حدود النصوص",
    showIgnored: "الواجهات المهملة",
    showFiltered: "النصوص المطابقة فقط",
    ocrOverlay: "تراكب النص",
    confidence: "مستوى الثقة",
    ignoredUI: "عنصر واجهة مهمل",
    compliantText: "نص مطابق معتمد",
    mediaError: "عذراً، تعذر تحميل المادة الإعلامية",
    currentFrame: "اللقطة الحالية",
    atTime: "عند"
  }
};

export default function OriginalMediaViewer({ session, apiPort, lang = 'en', selectedFrame = 0, setSelectedFrame }) {
  const isArabic = lang === 'ar';
  const labels = t[lang] || t.en;

  const frameScores = session.frame_scores || [];
  const isVideo = frameScores.length > 0;
  
  // View mode: 'video' or 'keyframes' for video assets
  const [viewMode, setViewMode] = useState(isVideo ? 'keyframes' : 'image');
  
  // Media URL resolver
  const getMediaUrl = (path) => {
    return `http://127.0.0.1:${apiPort}/media?path=${encodeURIComponent(path)}`;
  };

  // Zoom & Pan states
  const [zoom, setZoom] = useState(1.0);
  const [panX, setPanX] = useState(0);
  const [panY, setPanY] = useState(0);
  const [isDragging, setIsDragging] = useState(false);
  const dragStart = useRef({ x: 0, y: 0 });
  const containerRef = useRef(null);

  // Video playback sync states
  const videoRef = useRef(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [videoClosestFrameIndex, setVideoClosestFrameIndex] = useState(0);

  // Overlay filters
  const [hideOverlays, setHideOverlays] = useState(false);
  const [showBoxes, setShowBoxes] = useState(true);
  const [showIgnored, setShowIgnored] = useState(true);
  const [showCompliantOnly, setShowCompliantOnly] = useState(false);

  // Sync state if selectedFrame is changed from parent
  useEffect(() => {
    if (viewMode === 'keyframes' && videoRef.current) {
      videoRef.current.pause();
      setIsPlaying(false);
    }
  }, [selectedFrame, viewMode]);

  // Video timeline update handler
  const handleVideoTimeUpdate = () => {
    if (!videoRef.current) return;
    const time = videoRef.current.currentTime;
    setCurrentTime(time);
    
    // Map current time to closest keyframe index
    if (frameScores.length > 0) {
      const closestIdx = Math.min(
        frameScores.length - 1,
        Math.max(0, Math.round(time / 2.0))
      );
      setVideoClosestFrameIndex(closestIdx);
      if (setSelectedFrame) {
        setSelectedFrame(closestIdx);
      }
    }
  };

  const handleVideoLoadedMetadata = () => {
    if (videoRef.current) {
      setDuration(videoRef.current.duration);
    }
  };

  const togglePlay = () => {
    if (!videoRef.current) return;
    if (isPlaying) {
      videoRef.current.pause();
    } else {
      videoRef.current.play();
    }
    setIsPlaying(!isPlaying);
  };

  // Zoom actions
  const handleZoomIn = () => setZoom(prev => Math.min(prev + 0.25, 4.0));
  const handleZoomOut = () => {
    setZoom(prev => {
      const next = Math.max(prev - 0.25, 0.5);
      if (next === 1.0) {
        setPanX(0);
        setPanY(0);
      }
      return next;
    });
  };
  const handleResetZoom = () => {
    setZoom(1.0);
    setPanX(0);
    setPanY(0);
  };

  // Pan dragging
  const handleMouseDown = (e) => {
    if (zoom <= 1.0) return;
    setIsDragging(true);
    dragStart.current = { x: e.clientX - panX, y: e.clientY - panY };
  };

  const handleMouseMove = (e) => {
    if (!isDragging) return;
    setPanX(e.clientX - dragStart.current.x);
    setPanY(e.clientY - dragStart.current.y);
  };

  const handleMouseUp = () => setIsDragging(false);

  // Helper: check if OCR block text is flagged as Ignored UI
  const isBlockIgnored = (blockText) => {
    if (!blockText || !session.ignored_ui_text) return false;
    const textClean = blockText.trim().toLowerCase();
    return session.ignored_ui_text.some(ignored => {
      const ignoredClean = ignored.trim().toLowerCase();
      return textClean === ignoredClean || ignoredClean.includes(textClean) || textClean.includes(ignoredClean);
    });
  };

  // Format seconds to timeline string (MM:SS)
  const formatTime = (sec) => {
    const s = Math.floor(sec || 0);
    const m = Math.floor(s / 60);
    const rs = s % 60;
    return `${m.toString().padStart(2, '0')}:${rs.toString().padStart(2, '0')}`;
  };

  // Calculate relative bounding boxes
  const mediaWidth = session.media_context?.width || 1080;
  const mediaHeight = session.media_context?.height || 1920;

  const getRelativeBoxStyle = (box) => {
    if (!box || box.length < 4) return {};
    const xs = box.map(pt => pt[0]);
    const ys = box.map(pt => pt[1]);
    const xMin = Math.min(...xs);
    const xMax = Math.max(...xs);
    const yMin = Math.min(...ys);
    const yMax = Math.max(...ys);

    return {
      left: `${(xMin / mediaWidth) * 100}%`,
      top: `${(yMin / mediaHeight) * 100}%`,
      width: `${((xMax - xMin) / mediaWidth) * 100}%`,
      height: `${((yMax - yMin) / mediaHeight) * 100}%`
    };
  };

  // Determine active frame ID for rendering OCR overlays
  const activeFrameId = isVideo && frameScores[selectedFrame] 
    ? frameScores[selectedFrame].frame_id 
    : null;

  // Filter blocks based on sync frame (in Keyframes mode or synced Video playback)
  const allOcrBlocks = session.ocr_blocks || [];
  const activeOcrBlocks = allOcrBlocks.filter(block => {
    if (!isVideo) return true;
    if (viewMode === 'keyframes') {
      return block.frame_id === activeFrameId;
    } else {
      // Synced video mode: show blocks matching the closest keyframe
      const syncedFrameId = frameScores[videoClosestFrameIndex]?.frame_id;
      return block.frame_id === syncedFrameId;
    }
  });

  // Target media sources
  const originalMediaSrc = getMediaUrl(session.target_path);
  const activeKeyframeSrc = isVideo && frameScores[selectedFrame]
    ? getMediaUrl(`temp_frames/${frameScores[selectedFrame].frame_id}`)
    : originalMediaSrc;

  return (
    <div className={`original-viewer-card ${isArabic ? 'rtl' : ''}`}>
      {/* Top Toolbar */}
      <div className="viewer-toolbar">
        <div className="toolbar-section">
          {isVideo && (
            <div className="mode-toggle-group">
              <button 
                className={`toolbar-btn ${viewMode === 'keyframes' ? 'active' : ''}`}
                onClick={() => { setViewMode('keyframes'); handleResetZoom(); }}
              >
                <i className="fa-solid fa-images"></i> {labels.viewKeyframes}
              </button>
              <button 
                className={`toolbar-btn ${viewMode === 'video' ? 'active' : ''}`}
                onClick={() => { setViewMode('video'); handleResetZoom(); }}
              >
                <i className="fa-solid fa-video"></i> {labels.viewVideo}
              </button>
            </div>
          )}
          
          <div className="zoom-controls">
            <button className="icon-btn" onClick={handleZoomOut} title={labels.zoomOut} disabled={zoom <= 0.5}>
              <i className="fa-solid fa-magnifying-glass-minus"></i>
            </button>
            <span className="zoom-indicator">{Math.round(zoom * 100)}%</span>
            <button className="icon-btn" onClick={handleZoomIn} title={labels.zoomIn} disabled={zoom >= 4.0}>
              <i className="fa-solid fa-magnifying-glass-plus"></i>
            </button>
            {zoom !== 1.0 && (
              <button className="toolbar-text-btn" onClick={handleResetZoom}>
                {labels.reset}
              </button>
            )}
          </div>
        </div>

        {/* Quick status indicator */}
        <div className="toolbar-status">
          {isVideo && viewMode === 'keyframes' && (
            <span className="frame-badge">
              <i className="fa-solid fa-film"></i> {labels.currentFrame}: {selectedFrame + 1} ({formatTime(selectedFrame * 2.0)})
            </span>
          )}
          {isVideo && viewMode === 'video' && (
            <span className="frame-badge highlight">
              <i className="fa-solid fa-play"></i> {formatTime(currentTime)} / {formatTime(duration)}
            </span>
          )}
        </div>
      </div>

      {/* Main Canvas Area */}
      <div 
        className="viewer-canvas-container" 
        ref={containerRef}
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onMouseLeave={handleMouseUp}
        style={{ cursor: zoom > 1.0 ? (isDragging ? 'grabbing' : 'grab') : 'default', overflow: 'hidden', position: 'relative', width: '100%', height: '380px', backgroundColor: 'black', borderRadius: '8px' }}
      >
        <div 
          className="canvas-zoom-wrapper"
          style={{
            transform: `scale(${zoom}) translate(${panX / zoom}px, ${panY / zoom}px)`,
            transformOrigin: 'center center',
            transition: isDragging ? 'none' : 'transform 0.15s ease-out',
            position: 'relative',
            width: '100%',
            height: '100%',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center'
          }}
        >
          {/* Display element based on mode */}
          {viewMode === 'video' ? (
            <div className="media-element-wrapper" style={{ position: 'relative', height: '100%', aspectRatio: `${mediaWidth}/${mediaHeight}`, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <video 
                ref={videoRef}
                src={originalMediaSrc}
                className="viewer-video-element"
                onTimeUpdate={handleVideoTimeUpdate}
                onLoadedMetadata={handleVideoLoadedMetadata}
                onClick={togglePlay}
                style={{ width: '100%', height: '100%', objectFit: 'contain' }}
              />
              
              {/* OCR Bounding Boxes Layer */}
              {!hideOverlays && (
                <div className="ocr-overlays-container" style={{ position: 'absolute', top: 0, left: 0, width: '100%', height: '100%', pointerEvents: 'none' }}>
                  {activeOcrBlocks.map((block, idx) => {
                    const ignored = isBlockIgnored(block.text);
                    if (ignored && !showIgnored) return null;
                    if (showCompliantOnly && ignored) return null;

                    const boxStyle = getRelativeBoxStyle(block.box);
                    const boxClass = ignored ? 'ignored-box' : 'compliant-box';
                    const tooltipText = ignored 
                      ? `${labels.ignoredUI}: "${block.text}"`
                      : `${labels.compliantText}: "${block.text}" (${labels.confidence}: ${Math.round(block.confidence * 100)}%)`;

                    return (
                      <div 
                        key={idx} 
                        className={`ocr-overlay-box ${boxClass} ${showBoxes ? 'show-border' : ''}`}
                        style={{
                          ...boxStyle,
                          position: 'absolute',
                          pointerEvents: 'auto'
                        }}
                        title={tooltipText}
                      >
                        {showBoxes && (
                          <span className="ocr-box-label truncate">
                            {block.text}
                          </span>
                        )}
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          ) : (
            <div className="media-element-wrapper" style={{ position: 'relative', height: '100%', aspectRatio: `${mediaWidth}/${mediaHeight}`, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <img 
                src={activeKeyframeSrc} 
                className="viewer-image-element"
                alt="Active Target Analysis"
                draggable="false"
                style={{ width: '100%', height: '100%', objectFit: 'contain' }}
              />

              {/* OCR Bounding Boxes Layer */}
              {!hideOverlays && (
                <div className="ocr-overlays-container" style={{ position: 'absolute', top: 0, left: 0, width: '100%', height: '100%', pointerEvents: 'none' }}>
                  {activeOcrBlocks.map((block, idx) => {
                    const ignored = isBlockIgnored(block.text);
                    if (ignored && !showIgnored) return null;
                    if (showCompliantOnly && ignored) return null;

                    const boxStyle = getRelativeBoxStyle(block.box);
                    const boxClass = ignored ? 'ignored-box' : 'compliant-box';
                    const tooltipText = ignored 
                      ? `${labels.ignoredUI}: "${block.text}"`
                      : `${labels.compliantText}: "${block.text}" (${labels.confidence}: ${Math.round(block.confidence * 100)}%)`;

                    return (
                      <div 
                        key={idx} 
                        className={`ocr-overlay-box ${boxClass} ${showBoxes ? 'show-border' : ''}`}
                        style={{
                          ...boxStyle,
                          position: 'absolute',
                          pointerEvents: 'auto'
                        }}
                        title={tooltipText}
                      >
                        {showBoxes && (
                          <span className="ocr-box-label truncate">
                            {block.text}
                          </span>
                        )}
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Video controls / Scrubber Timeline */}
      {isVideo && viewMode === 'video' && (
        <div className="viewer-video-controls">
          <button className="play-control-btn" onClick={togglePlay}>
            <i className={`fa-solid ${isPlaying ? 'fa-pause' : 'fa-play'}`}></i>
          </button>
          
          <div className="custom-scrubber-wrapper">
            <input 
              type="range"
              min="0"
              max={duration || 100}
              value={currentTime}
              onChange={(e) => {
                if (videoRef.current) {
                  videoRef.current.currentTime = parseFloat(e.target.value);
                  setCurrentTime(parseFloat(e.target.value));
                }
              }}
              className="video-timeline-scrubber"
            />
            
            {/* Keyframe Markers Overlays */}
            <div className="timeline-keyframes-track">
              {frameScores.map((frame, idx) => {
                const markerTime = idx * 2.0;
                if (markerTime > duration) return null;
                const percent = (markerTime / duration) * 100;
                
                // Determine marker status (Strong Match or Borderline)
                const isMatch = frame.max_similarity >= session.threshold_used;
                const isBorderline = !isMatch && frame.max_similarity >= (session.threshold_used - 0.08);
                const markerClass = isMatch ? 'match' : (isBorderline ? 'borderline' : 'miss');

                return (
                  <button 
                    key={idx}
                    className={`keyframe-marker-tick ${markerClass} ${videoClosestFrameIndex === idx ? 'current' : ''}`}
                    style={{ left: `${percent}%` }}
                    onClick={() => {
                      if (videoRef.current) {
                        videoRef.current.currentTime = markerTime;
                        setCurrentTime(markerTime);
                        setVideoClosestFrameIndex(idx);
                      }
                    }}
                    title={`${labels.currentFrame} ${idx + 1} ${labels.atTime} ${formatTime(markerTime)} (${Math.round(frame.max_similarity * 100)}%)`}
                  />
                );
              })}
            </div>
          </div>
          
          <span className="time-display">{formatTime(currentTime)} / {formatTime(duration)}</span>
        </div>
      )}

      {/* Visibility Filters Controls Panel */}
      <div className="viewer-filter-controls">
        <label className="filter-checkbox-group">
          <input 
            type="checkbox"
            checked={hideOverlays}
            onChange={(e) => setHideOverlays(e.target.checked)}
          />
          <div className="custom-checkbox"></div>
          <span>{labels.hideOverlays}</span>
        </label>

        {!hideOverlays && (
          <>
            <label className="filter-checkbox-group">
              <input 
                type="checkbox"
                checked={showBoxes}
                onChange={(e) => setShowBoxes(e.target.checked)}
              />
              <div className="custom-checkbox"></div>
              <span>{labels.showBoxes}</span>
            </label>

            <label className="filter-checkbox-group">
              <input 
                type="checkbox"
                checked={showIgnored}
                onChange={(e) => setShowIgnored(e.target.checked)}
              />
              <div className="custom-checkbox"></div>
              <span>{labels.showIgnored}</span>
            </label>

            <label className="filter-checkbox-group">
              <input 
                type="checkbox"
                checked={showCompliantOnly}
                onChange={(e) => setShowCompliantOnly(e.target.checked)}
              />
              <div className="custom-checkbox"></div>
              <span>{labels.showFiltered}</span>
            </label>
          </>
        )}
      </div>
    </div>
  );
}
