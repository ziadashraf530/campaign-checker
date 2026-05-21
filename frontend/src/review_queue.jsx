import React, { useState, useEffect } from 'react';
import axios from 'axios';

const t = {
  en: {
    searchPlaceholder: "Search by file, campaign or reviewer...",
    sortDate: "Sort Date:",
    latestFirst: "Latest First",
    oldestFirst: "Oldest First",
    allAudits: "All Audits",
    needsReview: "Needs Review",
    highRisk: "High Risk",
    borderline: "Borderline",
    approved: "Approved",
    rejected: "Rejected",
    loading: "Loading persistent campaign audits...",
    emptyQueueTitle: "No audit records match filters",
    emptyQueueDesc: "Runs from visual matching will automatically log here.",
    mediaTarget: "Media Target",
    campaignBrief: "Campaign Brief",
    visualVerification: "Visual Verification",
    complianceVerdict: "Compliance Verdict",
    queueStatus: "Queue Status",
    reviewerSignature: "Reviewer Signature",
    auditTimestamp: "Audit Timestamp",
    actions: "Actions",
    pendingSignature: "Pending Signature",
    reviewBtn: "Review",
    deleteConfirm: "Are you sure you want to permanently delete this audit log?",
    failedToDelete: "Failed to delete: ",
    failedToFetch: "Failed to fetch QA history queue: ",
    na: "N/A"
  },
  ar: {
    searchPlaceholder: "ابحث بالملف، اسم الحملة أو المراجع...",
    sortDate: "ترتيب حسب التاريخ:",
    latestFirst: "الأحدث أولاً",
    oldestFirst: "الأقدم أولاً",
    allAudits: "كل التدقيقات",
    needsReview: "عايز مراجعة",
    highRisk: "خطر عالي",
    borderline: "على الحركرك",
    approved: "مية مية ومقبول",
    rejected: "مرفوض خالص",
    loading: "بنحمل سجلات مراجعة الحملات، ثواني...",
    emptyQueueTitle: "مافيش أي سجلات لايقة على التصفية دي",
    emptyQueueDesc: "أي تشغيل للمطابق البصري هينزل هنا علطول.",
    mediaTarget: "المادة المستهدفة",
    campaignBrief: "شروط وملخص الحملة",
    visualVerification: "التحقق البصري المكتشف",
    complianceVerdict: "قرار مطابقة النصوص",
    queueStatus: "حالة الطابور",
    reviewerSignature: "إمضاء وتوقيع المراجع",
    auditTimestamp: "تاريخ التدقيق والوقت",
    actions: "الإجراءات المتاحة",
    pendingSignature: "مستني التوقيع",
    reviewBtn: "مراجعة الجودة",
    deleteConfirm: "متأكد إنك عايز تمسح سجل المراجعة ده نهائي؟",
    failedToDelete: "مش قادرين نمسح السجل: ",
    failedToFetch: "مش عارفين نجيب طابور مراجعة الجودة: ",
    na: "مش متقيم"
  }
};

export default function ReviewQueue({ apiPort, onOpenWorkstation, refreshTrigger, lang = 'en' }) {
  const [sessions, setSessions] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [activeTab, setActiveTab] = useState('ALL'); // ALL, NEEDS_REVIEW, HIGH_RISK, BORDERLINE, APPROVED, REJECTED
  const [searchQuery, setSearchQuery] = useState('');
  const [sortBy, setSortBy] = useState('desc'); // desc, asc

  const labels = t[lang] || t.en;

  const fetchSessions = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await axios.get(`http://127.0.0.1:${apiPort}/analysis-history/`);
      setSessions(res.data || []);
    } catch (err) {
      setError(labels.failedToFetch + err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchSessions();
  }, [refreshTrigger, apiPort]);

  const handleDeleteSession = async (e, id) => {
    e.stopPropagation();
    if (!window.confirm(labels.deleteConfirm)) return;
    try {
      await axios.delete(`http://127.0.0.1:${apiPort}/analysis-history/${id}`);
      fetchSessions();
    } catch (err) {
      alert(labels.failedToDelete + err.message);
    }
  };

  // Compile tab category counts
  const getTabCounts = () => {
    const counts = {
      ALL: sessions.length,
      NEEDS_REVIEW: 0,
      HIGH_RISK: 0,
      BORDERLINE: 0,
      APPROVED: 0,
      REJECTED: 0
    };
    sessions.forEach(s => {
      const status = s.review_status || 'NEEDS_REVIEW';
      if (counts[status] !== undefined) {
        counts[status]++;
      }
    });
    return counts;
  };

  const counts = getTabCounts();

  // Filter and sort sessions
  const getFilteredSessions = () => {
    let filtered = [...sessions];

    // Filter by tab
    if (activeTab !== 'ALL') {
      filtered = filtered.filter(s => s.review_status === activeTab);
    }

    // Filter by search query
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      filtered = filtered.filter(s => 
        s.filename.toLowerCase().includes(q) ||
        s.campaign_name.toLowerCase().includes(q) ||
        (s.reviewed_by && s.reviewed_by.toLowerCase().includes(q))
      );
    }

    // Sort by timestamp
    filtered.sort((a, b) => {
      const tA = new Date(a.timestamp || 0).getTime();
      const tB = new Date(b.timestamp || 0).getTime();
      return sortBy === 'desc' ? tB - tA : tA - tB;
    });

    return filtered;
  };

  const filteredSessions = getFilteredSessions();

  const getFileIcon = (filename) => {
    if (!filename) return <i className="fa-solid fa-file"></i>;
    const ext = filename.split('.').pop().toLowerCase();
    if (['mp4', 'avi', 'mov', 'mkv', 'webm'].includes(ext)) {
      return <i className="fa-solid fa-video text-cyan"></i>;
    }
    return <i className="fa-solid fa-image text-indigo"></i>;
  };

  const formatTimestamp = (ts) => {
    if (!ts) return 'N/A';
    try {
      return new Date(ts).toLocaleString();
    } catch (e) {
      return ts;
    }
  };

  const getMatchTypeLabel = (matchType) => {
    if (lang === 'ar') {
      if (matchType === 'STRONG_MATCH') return 'تطابق قوي جداً';
      if (matchType === 'PROBABLE_STRONG_MATCH') return 'تطابق محتمل وقوي';
      if (matchType === 'POSSIBLE_MATCH') return 'تطابق حدي ممكن';
      return 'مافيش تطابق';
    }
    return matchType.replace('_', ' ');
  };

  const getComplianceStatusLabel = (status) => {
    if (lang === 'ar') {
      if (status === 'PASS') return 'ناجح وموافق للسياسة';
      if (status === 'PARTIAL') return 'موافق جزئياً';
      if (status === 'FAIL') return 'مخالف للسياسة';
      return status;
    }
    return status;
  };

  const getReviewStatusLabel = (status) => {
    const s = status || 'NEEDS_REVIEW';
    if (lang === 'ar') {
      if (s === 'NEEDS_REVIEW') return 'عايز مراجعة';
      if (s === 'HIGH_RISK') return 'خطر عالي';
      if (s === 'BORDERLINE') return 'على الحركرك';
      if (s === 'APPROVED') return 'مية مية ومقبول';
      if (s === 'REJECTED') return 'مرفوض خالص';
      return s;
    }
    return s.replace('_', ' ');
  };

  return (
    <div className="review-queue-panel">
      <div className="queue-controls">
        <div className="search-box">
          <i className="fa-solid fa-magnifying-glass search-icon"></i>
          <input 
            type="text" 
            placeholder={labels.searchPlaceholder} 
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="queue-search-input"
          />
        </div>
        
        <div className="sort-box">
          <label>{labels.sortDate}</label>
          <select 
            value={sortBy} 
            onChange={(e) => setSortBy(e.target.value)}
            className="queue-sort-select"
          >
            <option value="desc">{labels.latestFirst}</option>
            <option value="asc">{labels.oldestFirst}</option>
          </select>
        </div>
      </div>

      {/* Tabs list with count badges */}
      <div className="queue-tabs-bar">
        {[
          { key: 'ALL', label: labels.allAudits, icon: 'fa-box-archive' },
          { key: 'NEEDS_REVIEW', label: labels.needsReview, icon: 'fa-circle-question' },
          { key: 'HIGH_RISK', label: labels.highRisk, icon: 'fa-triangle-exclamation', pulse: true },
          { key: 'BORDERLINE', label: labels.borderline, icon: 'fa-arrows-split-up-and-left' },
          { key: 'APPROVED', label: labels.approved, icon: 'fa-circle-check' },
          { key: 'REJECTED', label: labels.rejected, icon: 'fa-circle-xmark' }
        ].map((t) => (
          <button 
            key={t.key} 
            onClick={() => setActiveTab(t.key)}
            className={`queue-tab-btn ${t.key.toLowerCase()} ${activeTab === t.key ? 'active' : ''}`}
          >
            <i className={`fa-solid ${t.icon} ${t.pulse ? 'pulse-icon' : ''}`}></i>
            <span>{t.label}</span>
            <span className="count-badge">{counts[t.key]}</span>
          </button>
        ))}
      </div>

      {error && <div className="error-banner">{error}</div>}

      {/* Queue Grid Table */}
      <div className="queue-table-card">
        {loading ? (
          <div className="loading-spinner-area">
            <i className="fa-solid fa-circle-notch fa-spin fa-2x spinner"></i>
            <p>{labels.loading}</p>
          </div>
        ) : filteredSessions.length === 0 ? (
          <div className="empty-queue-area">
            <i className="fa-solid fa-folder-open empty-icon"></i>
            <h3>{labels.emptyQueueTitle}</h3>
            <p>{labels.emptyQueueDesc}</p>
          </div>
        ) : (
          <div className="table-responsive">
            <table className="queue-table">
              <thead>
                <tr>
                  <th>{labels.mediaTarget}</th>
                  <th>{labels.campaignBrief}</th>
                  <th>{labels.visualVerification}</th>
                  <th>{labels.complianceVerdict}</th>
                  <th>{labels.queueStatus}</th>
                  <th>{labels.reviewerSignature}</th>
                  <th>{labels.auditTimestamp}</th>
                  <th>{labels.actions}</th>
                </tr>
              </thead>
              <tbody>
                {filteredSessions.map((session) => (
                  <tr 
                    key={session.analysis_id} 
                    onClick={() => onOpenWorkstation(session)}
                    className="queue-row"
                  >
                    <td>
                      <div className="media-cell">
                        {getFileIcon(session.filename)}
                        <span className="cell-filename truncate" title={session.filename}>{session.filename}</span>
                      </div>
                    </td>
                    <td><span className="badge-campaign-tag">{session.campaign_name}</span></td>
                    <td>
                      <div className="similarity-cell">
                        <span className="sim-percent">{Math.round(session.confidence_pct || 0)}%</span>
                        <span className={`sim-verdict-badge ${session.match_type.toLowerCase()}`}>
                          {getMatchTypeLabel(session.match_type)}
                        </span>
                      </div>
                    </td>
                    <td>
                      {session.compliance_status !== 'NOT_EVALUATED' ? (
                        <div className="comp-cell">
                          <span className={`badge-compliance ${session.compliance_status.toLowerCase()}`}>
                            {getComplianceStatusLabel(session.compliance_status)} ({session.compliance_score}/100)
                          </span>
                        </div>
                      ) : (
                        <span className="not-evaluated-txt">{labels.na}</span>
                      )}
                    </td>
                    <td>
                      <span className={`queue-status-badge ${(session.review_status || 'NEEDS_REVIEW').toLowerCase().replace('_', '-')}`}>
                        {getReviewStatusLabel(session.review_status)}
                      </span>
                    </td>
                    <td>
                      <span className="reviewer-name">{session.reviewed_by || labels.pendingSignature}</span>
                    </td>
                    <td className="timestamp-cell">{formatTimestamp(session.timestamp)}</td>
                    <td>
                      <div className="actions-cell" onClick={e => e.stopPropagation()}>
                        <button 
                          onClick={() => onOpenWorkstation(session)} 
                          className="action-btn open" 
                          title={labels.reviewBtn}
                        >
                          <i className="fa-solid fa-briefcase"></i> {labels.reviewBtn}
                        </button>
                        <button 
                          onClick={(e) => handleDeleteSession(e, session.analysis_id)} 
                          className="action-btn delete" 
                          title={lang === 'ar' ? 'حذف السجل' : 'Delete Session'}
                        >
                          <i className="fa-solid fa-trash-can"></i>
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
