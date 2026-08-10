/* ═══════════════════════════════════════════════════════════
   StepIndicator — Horizontal step wizard
   ═══════════════════════════════════════════════════════════ */
import { Upload, Settings, Download, Check } from 'lucide-react';
import { useI18n } from '../../i18n';
import './StepIndicator.css';

const steps = [
  { key: 1, icon: Upload, labelKey: 'step.import' },
  { key: 2, icon: Settings, labelKey: 'step.configure' },
  { key: 3, icon: Download, labelKey: 'step.export' },
];

export default function StepIndicator({ currentStep, onStepClick }) {
  const { t } = useI18n();

  return (
    <div className="step-indicator">
      {steps.map((step, i) => {
        const Icon = step.icon;
        const isActive = currentStep === step.key;
        const isCompleted = currentStep > step.key;
        const status = isActive ? 'active' : isCompleted ? 'completed' : 'pending';

        return (
          <div key={step.key} className="step-indicator-item">
            {i > 0 && (
              <div className={`step-connector ${isCompleted || isActive ? 'filled' : ''}`} />
            )}
            <button
              className={`step-circle ${status}`}
              onClick={() => onStepClick(step.key)}
              aria-label={t(step.labelKey)}
            >
              {isCompleted ? <Check size={14} strokeWidth={3} /> : <Icon size={14} />}
            </button>
            <span className={`step-label ${status}`}>{t(step.labelKey)}</span>
          </div>
        );
      })}
    </div>
  );
}
