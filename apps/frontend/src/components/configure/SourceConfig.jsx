import { useState } from 'react';
import { Database, ChevronDown, ChevronUp, Wifi, WifiOff, Key, Shield } from 'lucide-react';
import { useI18n } from '../../i18n';
import './SourceConfig.css';

const AUTH_TYPES = [
  { value: 'none', label: 'None' },
  { value: 'basic', label: 'Basic Auth' },
  { value: 'api_key', label: 'API Key' },
  { value: 'bearer', label: 'Bearer Token' },
];

export default function SourceConfig() {
  const { t } = useI18n();
  const [enabled, setEnabled] = useState(false);
  const [expanded, setExpanded] = useState(false);
  const [config, setConfig] = useState({
    scheme: 'https',
    host: '',
    port: '9200',
    index: '',
    scanId: '',
    searchText: '',
    authType: 'none',
    username: '',
    password: '',
    apiKey: '',
    bearerToken: '',
    size: '100',
    sslVerify: true,
  });

  const update = (field, value) => {
    setConfig(prev => ({ ...prev, [field]: value }));
  };

  const saveProfile = () => {
    const profiles = JSON.parse(localStorage.getItem('reporter_es_profiles') || '[]');
    const name = prompt('Tên profile:');
    if (!name) return;
    profiles.push({ name, config: { ...config } });
    localStorage.setItem('reporter_es_profiles', JSON.stringify(profiles));
  };

  const loadProfiles = () => {
    return JSON.parse(localStorage.getItem('reporter_es_profiles') || '[]');
  };

  return (
    <div className="source-config card">
      <div className="card__header">
        <Database size={18} />
        <h3>{t('configure.elastic')}</h3>
        <label className="toggle-label" style={{ marginLeft: 'auto' }}>
          <input type="checkbox" checked={enabled} onChange={(e) => setEnabled(e.target.checked)} />
          <span className="toggle-switch" />
        </label>
      </div>

      {enabled && (
        <div className="source-config__body">
          <div className="source-config__row">
            <div className="form-group" style={{ flex: '0 0 100px' }}>
              <label className="form-label">Scheme</label>
              <select
                className="form-input form-select"
                value={config.scheme}
                onChange={(e) => update('scheme', e.target.value)}
              >
                <option value="https">HTTPS</option>
                <option value="http">HTTP</option>
              </select>
            </div>
            <div className="form-group" style={{ flex: 1 }}>
              <label className="form-label">Host</label>
              <input
                className="form-input"
                value={config.host}
                onChange={(e) => update('host', e.target.value)}
                placeholder="elasticsearch.example.com"
              />
            </div>
            <div className="form-group" style={{ flex: '0 0 80px' }}>
              <label className="form-label">Port</label>
              <input
                className="form-input"
                value={config.port}
                onChange={(e) => update('port', e.target.value)}
                placeholder="9200"
              />
            </div>
          </div>

          <div className="form-group">
            <label className="form-label">Index</label>
            <input
              className="form-input"
              value={config.index}
              onChange={(e) => update('index', e.target.value)}
              placeholder="winlogbeat-*"
            />
          </div>

          <div className="source-config__row">
            <div className="form-group" style={{ flex: 1 }}>
              <label className="form-label">Scan ID</label>
              <input
                className="form-input"
                value={config.scanId}
                onChange={(e) => update('scanId', e.target.value)}
                placeholder="scan-001"
              />
            </div>
            <div className="form-group" style={{ flex: 1 }}>
              <label className="form-label">Search Text</label>
              <input
                className="form-input"
                value={config.searchText}
                onChange={(e) => update('searchText', e.target.value)}
                placeholder="keyword..."
              />
            </div>
          </div>

          <div className="form-group">
            <label className="form-label"><Key size={14} /> Authentication</label>
            <select
              className="form-input form-select"
              value={config.authType}
              onChange={(e) => update('authType', e.target.value)}
            >
              {AUTH_TYPES.map(a => (
                <option key={a.value} value={a.value}>{a.label}</option>
              ))}
            </select>
          </div>

          {config.authType === 'basic' && (
            <div className="source-config__row">
              <div className="form-group" style={{ flex: 1 }}>
                <label className="form-label">Username</label>
                <input className="form-input" value={config.username}
                  onChange={(e) => update('username', e.target.value)} />
              </div>
              <div className="form-group" style={{ flex: 1 }}>
                <label className="form-label">Password</label>
                <input className="form-input" type="password" value={config.password}
                  onChange={(e) => update('password', e.target.value)} />
              </div>
            </div>
          )}

          {config.authType === 'api_key' && (
            <div className="form-group">
              <label className="form-label">API Key</label>
              <input className="form-input" type="password" value={config.apiKey}
                onChange={(e) => update('apiKey', e.target.value)} />
            </div>
          )}

          {config.authType === 'bearer' && (
            <div className="form-group">
              <label className="form-label">Bearer Token</label>
              <input className="form-input" type="password" value={config.bearerToken}
                onChange={(e) => update('bearerToken', e.target.value)} />
            </div>
          )}

          <button
            className="source-config__advanced-toggle"
            onClick={() => setExpanded(!expanded)}
          >
            {expanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
            Advanced
          </button>

          {expanded && (
            <div className="source-config__advanced">
              <div className="form-group">
                <label className="form-label">Result Size</label>
                <input className="form-input" type="number" value={config.size}
                  onChange={(e) => update('size', e.target.value)} />
              </div>
              <div className="form-group form-group--inline">
                <label className="form-label"><Shield size={14} /> SSL Verify</label>
                <label className="toggle-label">
                  <input type="checkbox" checked={config.sslVerify}
                    onChange={(e) => update('sslVerify', e.target.checked)} />
                  <span className="toggle-switch" />
                </label>
              </div>
            </div>
          )}

          <div className="source-config__actions">
            <button className="btn btn--ghost btn--sm" onClick={saveProfile}>
              Save Profile
            </button>
          </div>
        </div>
      )}

      {!enabled && (
        <div className="source-config__disabled">
          <WifiOff size={24} strokeWidth={1.5} />
          <p>Elasticsearch source disabled</p>
        </div>
      )}
    </div>
  );
}
