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
    const file = new File(['[]'], 'fixture.csv');
    await expect(readValidationFixture(file)).rejects.toThrow('Fixture phải là tệp JSON');
  });
});
