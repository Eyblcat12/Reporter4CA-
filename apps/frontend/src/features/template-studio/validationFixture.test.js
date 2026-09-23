import { readValidationFixture } from './validationFixture';

describe('Template Studio validation fixture', () => {
  it('accepts an object with rows and metadata', async () => {
    const file = new File(
      [JSON.stringify({ rows: [{ hostname: 'PC-01' }], metadata: { project: 'Pilot' } })],
      'pilot.json',
      { type: 'application/json' },
    );

    await expect(readValidationFixture(file)).resolves.toEqual({
      filename: 'pilot.json',
      rows: [{ hostname: 'PC-01' }],
      metadata: { project: 'Pilot' },
    });
  });

  it('rejects invalid JSON and empty rows', async () => {
    await expect(readValidationFixture(new File(['{broken'], 'broken.json'))).rejects.toThrow(
      'Fixture JSON không hợp lệ',
    );
    await expect(
      readValidationFixture(new File([JSON.stringify({ rows: [] })], 'empty.json')),
    ).rejects.toThrow('mảng rows không rỗng');
  });

  it('rejects unrelated extensions before reading', async () => {
    const file = new File(['[]'], 'fixture.exe');
    await expect(readValidationFixture(file)).rejects.toThrow('Fixture phải là tệp JSON');
  });
  it('imports Tracking CSV using the real import API contract', async () => {
    vi.stubGlobal(
      'fetch',
      vi
        .fn()
        .mockResolvedValue({ ok: true, json: async () => ({ rows: [{ hostname: 'CSV-01' }] }) }),
    );
    try {
      await expect(
        readValidationFixture(new File(['hostname\nCSV-01'], 'tracking.csv')),
      ).resolves.toMatchObject({ rows: [{ hostname: 'CSV-01' }], metadata: {} });
      expect(fetch).toHaveBeenCalledWith(
        '/api/import-file',
        expect.objectContaining({ method: 'POST' }),
      );
      expect(fetch.mock.calls[0][0]).toBe('/api/column-preview');
    } finally {
      vi.unstubAllGlobals();
    }
  });

  it('passes detected columns and sheet to import without decoding file bytes as text', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          suggestedMapping: { 'Máy chủ': 'hostname_server' },
          headerRow: 2,
          sheetNames: ['Tracking'],
        }),
      })
      .mockResolvedValueOnce({ ok: true, json: async () => ({ rows: [{ hostname: 'SRV-01' }] }) });
    vi.stubGlobal('fetch', fetchMock);
    try {
      await readValidationFixture(new File([new Uint8Array([80, 75, 3, 4, 167])], 'Tracking.csv'));
      const body = JSON.parse(fetchMock.mock.calls[1][1].body);
      expect(body).toMatchObject({
        columnMapping: { 'Máy chủ': 'hostname_server' },
        headerRow: 2,
        sheetName: 'Tracking',
      });
      expect(body.contentBase64).toBe(JSON.parse(fetchMock.mock.calls[0][1].body).contentBase64);
    } finally {
      vi.unstubAllGlobals();
    }
  });
});
