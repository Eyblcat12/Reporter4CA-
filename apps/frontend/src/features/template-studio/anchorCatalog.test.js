import { anchorOptionsForSemantic, discoverTemplateAnchors } from './anchorCatalog';

const workspace = {
  analysis: {
    facts: {
      contentControls: [
        { value: 'CUSTOM_BLOCK', occurrences: 1 },
        { value: 'DUPLICATE', occurrences: 2 },
      ],
      bookmarks: [{ value: 'REPORT_BODY', occurrences: 1 }],
      tokens: ['{{REPORT_TITLE}}', '{{DUPLICATE_TOKEN}}'],
      tokenOccurrences: { '{{REPORT_TITLE}}': 1, '{{DUPLICATE_TOKEN}}': 3 },
    },
  },
  slots: [
    {
      semantic: 'overview',
      anchor: { kind: 'bookmark', value: 'REPORT_BODY' },
    },
  ],
};

describe('Template Studio anchor catalog', () => {
  it('offers every unique analyzed anchor and excludes ambiguous anchors', () => {
    expect(discoverTemplateAnchors(workspace)).toEqual({
      items: [
        { kind: 'content_control', value: 'CUSTOM_BLOCK', occurrences: 1 },
        { kind: 'bookmark', value: 'REPORT_BODY', occurrences: 1 },
        { kind: 'token', value: '{{REPORT_TITLE}}', occurrences: 1 },
      ],
      ambiguousCount: 2,
    });
  });

  it('puts suggestions first and marks anchors already used by another semantic', () => {
    const result = anchorOptionsForSemantic(workspace, 'report.title', [
      { kind: 'token', value: '{{REPORT_TITLE}}' },
    ]);

    expect(result.options[0]).toMatchObject({
      kind: 'token',
      value: '{{REPORT_TITLE}}',
      recommended: true,
      usedBy: '',
    });
    expect(result.options.find((item) => item.value === 'REPORT_BODY')).toMatchObject({
      recommended: false,
      usedBy: 'overview',
    });
  });
});
