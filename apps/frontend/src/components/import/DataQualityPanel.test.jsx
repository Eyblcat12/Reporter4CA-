import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { expect, it, vi } from 'vitest';
import DataQualityPanel from './DataQualityPanel';

vi.mock('../../i18n', () => ({ useI18n: () => ({ t: (key) => key }) }));

it('filters issues, opens a row and exposes safe bulk fixes', async () => {
  const user = userEvent.setup();
  const onFilter = vi.fn();
  const onIssue = vi.fn();
  const onTrimValues = vi.fn();
  const onFillResult = vi.fn();
  const issue = { row: 2, field: 'hostname', level: 'error', code: 'missing_hostname', message: 'Missing host' };
  render(<DataQualityPanel
    quality={{
      valid: false,
      issues: [issue],
      summary: {
        validRows: 1, errorRows: 1, warningRows: 1, duplicateHostnames: 0,
        invalidIps: 0, missingOs: 1, missingResult: 1,
      },
    }}
    activeFilter="all"
    onFilter={onFilter}
    onIssue={onIssue}
    onTrimValues={onTrimValues}
    onFillResult={onFillResult}
  />);

  await user.click(screen.getByText('quality.errors'));
  expect(onFilter).toHaveBeenCalledWith('errors');
  await user.click(screen.getByText('Missing host'));
  expect(onIssue).toHaveBeenCalledWith(issue);
  await user.click(screen.getByText('quality.trim'));
  await user.click(screen.getByText('quality.fillResult'));
  expect(onTrimValues).toHaveBeenCalledOnce();
  expect(onFillResult).toHaveBeenCalledOnce();
});
