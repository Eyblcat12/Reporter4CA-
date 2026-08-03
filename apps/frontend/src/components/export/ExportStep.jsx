/* ═══════════════════════════════════════════════════════════
   ExportStep — Stats top, two-column body + DOCX preview modal
   ═══════════════════════════════════════════════════════════ */
import { motion } from 'framer-motion';
import ReportTypeSelector from './ReportTypeSelector';
import PreviewPanel from './PreviewPanel';
import GenerateButton from './GenerateButton';
import DocxPreviewModal from './DocxPreviewModal';
import StatsBar from '../shared/StatsBar';
import './ExportStep.css';

export default function ExportStep() {
  return (
    <div className="export-step">
      {/* Top: Stats Overview */}
      <motion.div
        className="export-step__top"
        initial={{ opacity: 0, y: -10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3, ease: [0.16, 1, 0.3, 1] }}
      >
        <StatsBar />
      </motion.div>

      {/* Body: Two-column grid */}
      <div className="export-step__body">
        <motion.div
          className="export-step__left"
          initial={{ opacity: 0, x: -16 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.4, delay: 0.1, ease: [0.16, 1, 0.3, 1] }}
        >
          <ReportTypeSelector />
          <GenerateButton />
        </motion.div>

        <motion.div
          className="export-step__right"
          initial={{ opacity: 0, x: 16 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.4, delay: 0.15, ease: [0.16, 1, 0.3, 1] }}
        >
          <PreviewPanel />
        </motion.div>
      </div>

      {/* DOCX Preview Modal (renders on top when active) */}
      <DocxPreviewModal />
    </div>
  );
}
