import { useRef, useState } from 'react'
import axios from 'axios'

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
        debug: siglipDebug
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
        return <span className="badge strong"><i className="fa-solid fa-circle-check"></i> Strong Match</span>
      case 'PROBABLE_STRONG_MATCH':
        return <span className="badge probable"><i className="fa-solid fa-circle-check"></i> Probable Match</span>
      case 'POSSIBLE_MATCH':
        return <span className="badge possible"><i className="fa-solid fa-circle-question"></i> Possible Match</span>
      default:
        return <span className="badge none"><i className="fa-solid fa-circle-xmark"></i> No Match</span>
    }
  }

  // Get matching classification CSS state
  const getMatchClass = (matchType) => {
    if (matchType === 'STRONG_MATCH') return 'strong';
    if (matchType === 'PROBABLE_STRONG_MATCH') return 'probable';
    if (matchType === 'POSSIBLE_MATCH') return 'possible';
    return 'none';
  }

  return (
    <div className="app-container">
      {/* Top Header */}
      <header>
        <div className="logo-section">
          <h1><i className="fa-solid fa-bolt-lightning"></i> Campaign Checker</h1>
          <p>Next-gen visual verification & campaign matching platform</p>
        </div>
        <div className="engine-badge">
          <span></span> SigLIP v1.2 Engine Active
        </div>
      </header>

      {/* Main Grid: Control Panel (Left) & Results Display (Right) */}
      <main className="dashboard-grid">
        
        {/* Left Side: Parameters / Control Panel */}
        <section className="panel-card">
          <h2><i className="fa-solid fa-sliders"></i> Control Center</h2>

          {/* API Server Port Config */}
          <div className="form-group" style={{ marginBottom: '1.25rem' }}>
            <label>API Server Port</label>
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
              <i className="fa-solid fa-fingerprint"></i> SigLIP Matcher
            </button>
            <button 
              className={`mode-btn ${mode === 'legacy' ? 'active' : ''}`}
              onClick={() => { setMode('legacy'); setError(null); }}
            >
              <i className="fa-solid fa-magnifying-glass"></i> Legacy Analyzer
            </button>
          </div>

          {/* Mode-specific forms */}
          {mode === 'siglip' ? (
            <div>
              <div className="form-group">
                <label>Reference Campaign Directory</label>
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
                <label>Target File or Folder Path</label>
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
                <label>Campaign Tag / Name</label>
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

              <label className="checkbox-group">
                <input 
                  type="checkbox"
                  checked={siglipDebug}
                  onChange={(e) => setSiglipDebug(e.target.checked)}
                />
                <div className="custom-checkbox"></div>
                <span>Export debug files to backend</span>
              </label>

              <button 
                className="btn-primary" 
                onClick={runSiglipMatching}
                disabled={loading}
              >
                {loading ? (
                  <>
                    <i className="fa-solid fa-circle-notch fa-spin"></i> Analyzing...
                  </>
                ) : (
                  <>
                    <i className="fa-solid fa-wand-magic-sparkles"></i> Verify Campaign
                  </>
                )}
              </button>
            </div>
          ) : (
            <div>
              <div className="form-group">
                <label>Brand Name to Search</label>
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
                <label>Target File or Folder (Optional)</label>
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
                <label>Reference Logos Path (Optional)</label>
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
                    <i className="fa-solid fa-circle-notch fa-spin"></i> Scanning Logos...
                  </>
                ) : (
                  <>
                    <i className="fa-solid fa-search"></i> Run Logo Analysis
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
              <h3>AI Engine In Progress</h3>
              <p>Extracting keyframes, generating SigLIP embeddings, and computing multi-factor cosine similarities...</p>
            </div>
          )}

          {/* State 2: Welcome / Empty */}
          {!loading && !siglipData && legacyResults.length === 0 && (
            <div className="empty-state">
              <i className="fa-solid fa-robot empty-state-icon"></i>
              <h3>Ready for Verification</h3>
              <p>Configure your reference campaign directory and targets in the Control Center, then execute verification to receive structured visual reports.</p>
            </div>
          )}

          {/* State 3: SigLIP Results Display */}
          {!loading && siglipData && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
              
              {/* Summary Metrics Card */}
              <div className="summary-card">
                <div className="summary-header">
                  <div className="summary-title">
                    <h3>Campaign Match Report</h3>
                    <span>{siglipData.summary?.campaign_name || 'Verification'}</span>
                  </div>
                  <div className="engine-badge" style={{ borderColor: 'var(--accent-muted)' }}>
                    {siglipData.summary?.num_references} references loaded
                  </div>
                </div>

                <div className="summary-stats">
                  <div className="stat-item">
                    <div className="stat-val accent">{siglipData.summary?.num_targets}</div>
                    <div className="stat-label">Total Targets</div>
                  </div>
                  <div className="stat-item">
                    <div className="stat-val strong">{siglipData.summary?.strong_matches}</div>
                    <div className="stat-label">Strong Matches</div>
                  </div>
                  <div className="stat-item">
                    <div className="stat-val possible">{siglipData.summary?.possible_matches}</div>
                    <div className="stat-label">Possible Matches</div>
                  </div>
                  <div className="stat-item">
                    <div className="stat-val none">{siglipData.summary?.rejections}</div>
                    <div className="stat-label">Rejections</div>
                  </div>
                </div>

                <div className="info-row">
                  <i className="fa-solid fa-circle-info"></i>
                  <span>Reference bank variance: <strong>{siglipData.summary?.reference_variance}</strong>. Lower variance indicates highly consistent references (strict threshold).</span>
                </div>
              </div>

              {/* Reference Set Quality Card */}
              {siglipData.summary?.cohesion_metrics && (
                <div className="cohesion-panel">
                  <div className="cohesion-header">
                    <div className="cohesion-title"><i className="fa-solid fa-gem"></i> Reference Set Quality</div>
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
                        Detected Platforms
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
                              <i className={platformIcon}></i> {platformLabel}: {count} {count === 1 ? 'post' : 'posts'}
                            </span>
                          );
                        })}
                      </div>
                    </div>
                  )}
                </div>
              )}

              {/* Individual Target Cards list */}
              <div className="results-header">Target Verification List</div>
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
                              </div>
                              {res.media_context && (
                                <div className="media-badges-row">
                                  <span className="media-badge">
                                    <i className="fa-solid fa-expand"></i> Aspect: {res.media_context.aspect_ratio?.toFixed(2)}
                                  </span>
                                  {res.media_context.is_social_media && (
                                    <span className="media-badge highlight">
                                      <i className="fa-solid fa-share-nodes"></i> Social Format
                                    </span>
                                  )}
                                  {res.media_context.has_overlays && (
                                    <span className="media-badge warning">
                                      <i className="fa-solid fa-rectangle-ad"></i> Overlay
                                    </span>
                                  )}
                                  {res.media_context.compression_level > 0.4 && (
                                    <span className="media-badge">
                                      <i className="fa-solid fa-compress"></i> Noise: {Math.round(res.media_context.compression_level * 100)}%
                                    </span>
                                  )}
                                  {res.media_context.suggested_threshold_offset < 0 && (
                                    <span className="media-badge highlight">
                                      <i className="fa-solid fa-sliders"></i> Offset: {res.media_context.suggested_threshold_offset?.toFixed(2)}
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
                                <i className="fa-solid fa-chart-line"></i> Similarity Metrics
                              </div>
                              <div className="matching-highlights">
                                <div className="highlight-box">
                                  <span className="highlight-label">Overall Match Verdict</span>
                                  <span className="highlight-val">{res.verdict}</span>
                                </div>
                                <div className="highlight-box">
                                  <span className="highlight-label">Primary Blended Score</span>
                                  <span className="highlight-val mono">{(res.confidence).toFixed(4)}</span>
                                </div>
                                <div className="highlight-box">
                                  <span className="highlight-label">Max Similarity Found</span>
                                  <span className="highlight-val mono">{(res.top_similarity).toFixed(4)}</span>
                                </div>
                                <div className="highlight-box">
                                  <span className="highlight-label">Average Similarity</span>
                                  <span className="highlight-val mono">{(res.average_similarity).toFixed(4)}</span>
                                </div>
                                <div className="highlight-box">
                                  <span className="highlight-label">Threshold Applied</span>
                                  <span className="highlight-val mono">{(res.threshold_used).toFixed(4)}</span>
                                </div>
                                <div className="highlight-box">
                                  <span className="highlight-label">Frames Evaluated</span>
                                  <span className="highlight-val">{res.num_frames_analyzed}</span>
                                </div>
                                {res.best_reference && (
                                  <div className="highlight-box">
                                    <span className="highlight-label">Best Reference Image</span>
                                    <span className="highlight-val" style={{ maxWidth: '180px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={res.best_reference}>
                                      {res.best_reference}
                                    </span>
                                  </div>
                                )}
                                <div className="highlight-box">
                                  <span className="highlight-label">Compute Time</span>
                                  <span className="highlight-val">{res.processing_time_ms} ms</span>
                                </div>
                              </div>
                            </div>

                            {/* Reference Matching Breakdown */}
                            <div>
                              <div className="detail-section-title">
                                <i className="fa-solid fa-cubes"></i> Reference Matching Breakdown
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
                                <i className="fa-solid fa-shield-halved"></i> Brand Conflict & Proximity
                              </div>
                              <div className="matching-highlights">
                                <div className="highlight-box-vertical">
                                  <div className="highlight-vertical-header">
                                    <span className="highlight-label">Competitor Proximity Index</span>
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
                                      Nearest Competitor Asset: <strong>{res.explainability.best_competitor}</strong>
                                    </div>
                                  )}
                                </div>

                                <div className="highlight-box-vertical">
                                  <div className="highlight-vertical-header">
                                    <span className="highlight-label">Decision Ambiguity Index</span>
                                    <span className="highlight-val mono">{(res.ambiguity_score || 0.0).toFixed(4)}</span>
                                  </div>
                                  <div className="competitor-track">
                                    <div 
                                      className={`competitor-fill ${res.ambiguity_score > 0.60 ? 'danger' : res.ambiguity_score > 0.30 ? 'warning' : 'safe'}`}
                                      style={{ width: `${(res.ambiguity_score || 0.0) * 100}%` }}
                                    ></div>
                                  </div>
                                  <div className="competitor-meta-info">
                                    Status: <strong className={res.ambiguity_score > 0.5 ? 'txt-danger' : 'txt-safe'}>{res.ambiguity_score > 0.5 ? 'AMBIGUOUS MATCH PATTERN' : 'HIGH RETRIEVAL MARGIN'}</strong>
                                  </div>
                                </div>
                              </div>
                            </div>

                            {/* Diagnostics Panel & Warnings */}
                            <div>
                              <div className="detail-section-title">
                                <i className="fa-solid fa-stethoscope"></i> Diagnostic & Explainability Logs
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
                                    <strong>All Retrieval Diagnostics Nominal:</strong> Verification metrics confirmed clear decision boundaries. No competitor distractor encroachment detected.
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
                                <i className="fa-solid fa-chart-line"></i> Platt scaling calibration
                              </div>
                              <div className="calibration-stat-row">
                                <span className="calibration-stat-label">Calibrated Probability</span>
                                <span className={`calibration-stat-val ${res.match_type === 'STRONG_MATCH' ? 'highlight-green' : res.match_type === 'PROBABLE_STRONG_MATCH' ? 'highlight-gold' : ''}`}>
                                  {res.confidence_pct}%
                                </span>
                              </div>
                              <div className="calibration-stat-row">
                                <span className="calibration-stat-label">Raw Max Similarity</span>
                                <span className="calibration-stat-val">{res.top_similarity?.toFixed(4)}</span>
                              </div>
                              <div className="calibration-stat-row">
                                <span className="calibration-stat-label">Raw Avg Similarity</span>
                                <span className="calibration-stat-val">{res.average_similarity?.toFixed(4)}</span>
                              </div>
                              <div className="calibration-stat-row">
                                <span className="calibration-stat-label">Active Threshold</span>
                                <span className="calibration-stat-val">{res.threshold_used?.toFixed(4)}</span>
                              </div>
                              <div className="calibration-stat-row">
                                <span className="calibration-stat-label">Decision Margin</span>
                                <span className="calibration-stat-val">{(res.confidence - res.threshold_used)?.toFixed(4)}</span>
                              </div>
                            </div>

                            {/* Calibration Card 2: Temporal Stability */}
                            <div className="calibration-card">
                              <div className="calibration-card-header">
                                <i className="fa-solid fa-clock-rotate-left"></i> Temporal stability info
                              </div>
                              <div className="calibration-stat-row">
                                <span className="calibration-stat-label">Temporal Continuity Strength</span>
                                <span className="calibration-stat-val highlight-green">
                                  {(res.temporal_strength || 0.0)?.toFixed(4)}
                                </span>
                              </div>
                              <div className="calibration-stat-row">
                                <span className="calibration-stat-label">Frames Evaluated</span>
                                <span className="calibration-stat-val">{res.num_frames_analyzed}</span>
                              </div>
                              <div className="calibration-stat-row">
                                <span className="calibration-stat-label">Stable Segments Count</span>
                                <span className="calibration-stat-val">{res.stable_segments ? res.stable_segments.length : 0}</span>
                              </div>
                              <div className="calibration-stat-row">
                                <span className="calibration-stat-label">Best Match Frame ID</span>
                                <span className="calibration-stat-val" style={{ maxWidth: '160px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={res.best_frame}>
                                  {res.best_frame || 'N/A'}
                                </span>
                              </div>
                              <div className="calibration-stat-row">
                                <span className="calibration-stat-label">Diagnostics Status</span>
                                <span className="calibration-stat-val">{res.warnings && res.warnings.length > 0 ? 'WARNINGS FLAGGED' : 'NOMINAL'}</span>
                              </div>
                            </div>

                            {/* Calibration Card 3: Reference Cluster & Boost Telemetry */}
                            <div className="calibration-card">
                              <div className="calibration-card-header">
                                <i className="fa-solid fa-cubes"></i> Semantic Cluster & Adjustments
                              </div>
                              <div className="calibration-stat-row">
                                <span className="calibration-stat-label">Dominant Cluster Group</span>
                                <span className="calibration-stat-val" style={{ color: 'var(--accent-light)' }}>
                                  {(() => {
                                    const cl = res.dominant_cluster;
                                    if (cl === 'logo_refs') return 'Logo References';
                                    if (cl === 'drink_refs') return 'Drink References';
                                    if (cl === 'product_refs') return 'Product References';
                                    if (cl === 'store_refs') return 'Store References';
                                    return cl || 'Global Centroid';
                                  })()}
                                </span>
                              </div>
                              <div className="calibration-stat-row">
                                <span className="calibration-stat-label">Cluster Centroid Similarity</span>
                                <span className="calibration-stat-val">
                                  {res.cluster_similarity !== undefined && res.cluster_similarity !== null ? res.cluster_similarity.toFixed(4) : '0.0000'}
                                </span>
                              </div>
                              <div className="calibration-stat-row">
                                <span className="calibration-stat-label">Social UI Adjustment</span>
                                <span className={`calibration-stat-val ${res.social_adjustment > 0 ? 'highlight-green' : ''}`}>
                                  {res.social_adjustment > 0 ? `+${res.social_adjustment.toFixed(3)}` : '0.000'}
                                </span>
                              </div>
                              <div className="calibration-stat-row">
                                <span className="calibration-stat-label">Branding Product Boost</span>
                                <span className={`calibration-stat-val ${res.product_boost > 0 ? 'highlight-green' : ''}`}>
                                  {res.product_boost > 0 ? `+${res.product_boost.toFixed(3)}` : '0.000'}
                                </span>
                              </div>
                              <div className="calibration-stat-row">
                                <span className="calibration-stat-label">Calibration Adjustments</span>
                                <span className="calibration-stat-val">
                                  {res.social_adjustment > 0 || res.product_boost > 0 ? 'ACTIVE BOOSTS' : 'NOMINAL'}
                                </span>
                              </div>
                            </div>
                          </div>

                          {/* Model Decision Reasoning Chain */}
                          {res.explainability?.reasoning_steps && (
                            <div>
                              <div className="detail-section-title">
                                <i className="fa-solid fa-brain"></i> Model Decision Reasoning Chain
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
                                <i className="fa-solid fa-chart-area"></i> Temporal Verification & Retrieval Timeline
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
                                        <text x="755" y={yThresh + 3} fill="var(--match-possible)" fontSize="9" fontWeight="bold">THR: {res.threshold_used.toFixed(2)}</text>
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
                                        <title>{`Frame: ${frame.frame_id}\nRaw Score: ${(frame.raw_score !== undefined ? frame.raw_score : frame.max_similarity).toFixed(3)}\nSmoothed: ${smVal.toFixed(3)}\nCompetitor Proximity: ${(frame.competitor_similarity !== undefined ? frame.competitor_similarity : 0.0).toFixed(3)}\nBest Reference: ${frame.best_reference}`}</title>
                                      </g>
                                    )
                                  })}
                                </svg>
                              </div>
                              
                              {/* Dynamic Legend */}
                              <div className="timeline-legend">
                                <div className="legend-item"><span className="legend-dot raw"></span> Raw Frame Score</div>
                                <div className="legend-item"><span className="legend-dot smoothed"></span> Smoothed Match Score</div>
                                <div className="legend-item"><span className="legend-dot competitor"></span> Competitor Proximity</div>
                                <div className="legend-item"><span className="legend-dot thresh"></span> Match Threshold</div>
                              </div>

                              {/* Active Matching Timeline Segment Pills */}
                              {res.stable_segments && res.stable_segments.length > 0 && (
                                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem', marginTop: '0.75rem', justifyContent: 'center' }}>
                                  {res.stable_segments.map((seg, sIdx) => (
                                    <span key={sIdx} className="media-badge highlight" style={{ fontSize: '0.8rem', padding: '0.35rem 0.65rem' }}>
                                      <i className="fa-solid fa-circle-play"></i> Segment {sIdx + 1}: Frames {seg.start_frame}-{seg.end_frame} ({seg.duration_frames}f) | Avg: {(seg.average_score * 100).toFixed(1)}%
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
                                <i className="fa-solid fa-photo-film"></i> Extracted Frame Analysis
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
              <div className="results-header">Legacy Analysis Results</div>
              <div className="results-list">
                {legacyResults.map((r, i) => (
                  <div className="result-card STRONG_MATCH" key={i} style={{ borderLeft: '4px solid var(--accent)' }}>
                    <div className="result-main" style={{ cursor: 'default' }}>
                      <div className="result-meta">
                        <div className="file-info">
                          {getFileTypeIcon(r.file)}
                          <span className="file-name" style={{ maxWidth: '350px' }}>{r.file.split(/[\\/]/).pop()}</span>
                          <span className="badge legacy">{r.influencer || 'Post'} ({r.platform || 'Platform'})</span>
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
    </div>
  )
}
