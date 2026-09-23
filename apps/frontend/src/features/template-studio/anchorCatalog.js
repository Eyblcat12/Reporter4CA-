const KIND_ORDER = { content_control: 0, bookmark: 1, token: 2 };
const SEMANTIC_ALIASES = { remediation: ['token:{{REMEDIATION_REGISTER}}'] };

export function anchorKey(anchor) {
  return `${anchor.kind}:${anchor.value}`;
}

function compareAnchors(left, right) {
  return (
    (KIND_ORDER[left.kind] ?? 99) - (KIND_ORDER[right.kind] ?? 99) ||
    left.value.localeCompare(right.value)
  );
}

export function discoverTemplateAnchors(workspace) {
  const facts = workspace?.analysis?.facts || {};
  const candidates = [
    ...(facts.contentControls || []).map((item) => ({
      kind: 'content_control',
      value: item.value,
      occurrences: Number(item.occurrences ?? 1),
    })),
    ...(facts.bookmarks || []).map((item) => ({
      kind: 'bookmark',
      value: item.value,
      occurrences: Number(item.occurrences ?? 1),
    })),
    ...(facts.tokens || []).map((value) => ({
      kind: 'token',
      value,
      occurrences: Number(facts.tokenOccurrences?.[value] ?? 1),
    })),
  ].filter((item) => item.value);
  const unique = new Map();
  let ambiguousCount = 0;
  for (const candidate of candidates) {
    if (candidate.occurrences !== 1) {
      ambiguousCount += 1;
      continue;
    }
    unique.set(anchorKey(candidate), candidate);
  }
  return { items: [...unique.values()].sort(compareAnchors), ambiguousCount };
}

export function anchorOptionsForSemantic(workspace, semantic, suggestions = []) {
  const catalog = discoverTemplateAnchors(workspace);
  const recommendationKeys = new Set([
    ...suggestions.map(anchorKey),
    ...(SEMANTIC_ALIASES[semantic] || []),
  ]);
  const used = new Map(
    (workspace?.slots || [])
      .filter((slot) => slot.semantic !== semantic && slot.anchor)
      .map((slot) => [anchorKey(slot.anchor), slot.semantic]),
  );
  const options = catalog.items.map((anchor) => ({
    ...anchor,
    recommended: recommendationKeys.has(anchorKey(anchor)),
    usedBy: used.get(anchorKey(anchor)) || '',
  }));
  for (const suggestion of suggestions) {
    if (!options.some((anchor) => anchorKey(anchor) === anchorKey(suggestion))) {
      options.push({
        kind: suggestion.kind,
        value: suggestion.value,
        occurrences: 1,
        recommended: true,
        usedBy: used.get(anchorKey(suggestion)) || '',
      });
    }
  }
  const current = (workspace?.slots || []).find((slot) => slot.semantic === semantic)?.anchor;
  if (current && !options.some((anchor) => anchorKey(anchor) === anchorKey(current))) {
    options.push({ ...current, occurrences: 1, recommended: false, usedBy: '' });
  }
  options.sort(
    (left, right) =>
      Number(right.recommended) - Number(left.recommended) || compareAnchors(left, right),
  );
  return { options, ambiguousCount: catalog.ambiguousCount };
}
