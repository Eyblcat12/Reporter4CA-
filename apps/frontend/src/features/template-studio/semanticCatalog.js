export const SEMANTIC_CATALOG = {
  'report.title': {
    label: 'Tiêu đề báo cáo',
    renderer: 'text',
    source: 'metadata.title',
    fields: [],
  },
  overview: {
    label: 'Tổng quan',
    renderer: 'rich_text',
    source: 'analysis.overview',
    fields: [],
  },
  investigation: {
    label: 'Phân tích và điều tra',
    renderer: 'finding_sections',
    source: 'analysis.findings',
    fields: [],
  },
  remediation: {
    label: 'Gỡ bỏ mã độc',
    renderer: 'remediation_table',
    source: 'analysis.affected_assets',
    fields: ['hostname', 'ip', 'status'],
  },
  ioc: {
    label: 'Chỉ dấu xâm nhập',
    renderer: 'ioc_table',
    source: 'analysis.iocs',
    fields: ['type', 'value'],
  },
  recommendations: {
    label: 'Khuyến nghị',
    renderer: 'rich_text',
    source: 'analysis.recommendations',
    fields: [],
  },
  'inventory.server': {
    label: 'Danh sách máy chủ',
    renderer: 'asset_table',
    source: 'assets.servers',
    fields: ['hostname', 'ip', 'os'],
  },
  'inventory.client': {
    label: 'Danh sách máy trạm',
    renderer: 'asset_table',
    source: 'assets.clients',
    fields: ['hostname', 'ip', 'os'],
  },
  'results.server': {
    label: 'Kết quả máy chủ',
    renderer: 'result_table',
    source: 'analysis.server_results',
    fields: ['hostname', 'result'],
  },
  'results.client': {
    label: 'Kết quả máy trạm',
    renderer: 'result_table',
    source: 'analysis.client_results',
    fields: ['hostname', 'result'],
  },
  'results.summary': {
    label: 'Tổng hợp kết quả',
    renderer: 'summary_table',
    source: 'analysis.summary',
    fields: [],
  },
  findings: {
    label: 'Phát hiện',
    renderer: 'finding_table',
    source: 'analysis.findings',
    fields: [],
  },
  'incident.info': {
    label: 'Thông tin sự cố',
    renderer: 'field_group',
    source: 'incident.info',
    fields: [],
  },
  executive_summary: {
    label: 'Tóm tắt điều hành',
    renderer: 'rich_text',
    source: 'incident.executive_summary',
    fields: [],
  },
  affected_assets: {
    label: 'Tài sản bị ảnh hưởng',
    renderer: 'asset_table',
    source: 'incident.affected_assets',
    fields: ['hostname', 'ip'],
  },
  timeline: {
    label: 'Dòng thời gian',
    renderer: 'timeline_table',
    source: 'incident.timeline',
    fields: ['timestamp', 'event', 'evidence'],
  },
  mitre: {
    label: 'MITRE ATT&CK',
    renderer: 'mitre_table',
    source: 'incident.mitre',
    fields: ['technique_id', 'technique', 'tactic'],
  },
  response: {
    label: 'Ứng phó sự cố',
    renderer: 'response_sections',
    source: 'incident.response',
    fields: [],
  },
  lessons: {
    label: 'Bài học kinh nghiệm',
    renderer: 'rich_text',
    source: 'incident.lessons_learned',
    fields: [],
  },
};

export function semanticDefinition(semantic) {
  return (
    SEMANTIC_CATALOG[semantic] || {
      label: semantic,
      renderer: 'unknown',
      source: 'unknown',
      fields: [],
    }
  );
}
