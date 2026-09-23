import referenceHtml from './stitch-reference.html?raw';
import compiledCss from './stitch-reference.generated.css?raw';
import styles from './TemplateStudioNext.module.css';

// Reviewed local fixture only: never substitute customer HTML into srcDoc.
export const comparisonDocument = referenceHtml.replace(
  '<head>',
  `<head><style>${compiledCss}</style>`,
);

export default function TemplateStudioNext({ onCompare, onReturn }) {
  return (
    <section className={styles.root} aria-label="Template Studio UI mới — so sánh">
      <nav className={styles.compare} aria-label="So sánh giao diện Studio">
        <div>
          <strong>UI mới</strong>
          <span>Chỉ xem thiết kế · dữ liệu mẫu · không lưu vào tool</span>
        </div>
        <div>
          <a href="?view=template-studio" onClick={onCompare}>
            Xem UI hiện tại
          </a>
          <a href="./" onClick={onReturn}>
            Về báo cáo
          </a>
        </div>
      </nav>
      <iframe
        className={styles.frame}
        title="Mẫu Stitch — Mapping Workspace"
        srcDoc={comparisonDocument}
        sandbox=""
        referrerPolicy="no-referrer"
      />
    </section>
  );
}
