import { describe, expect, it, vi } from 'vitest';
import { act, fireEvent, screen, waitFor } from '@testing-library/react';
import { renderWithProviders } from './utils';
import { backupApi, BACKUP_INFO } from './mocks/api';
import BackupRestore from '../pages/BackupRestore';

const DUMP_REVISION = '3d6f19fc27d2';

function dumpContent(revision: string): string {
  return [
    `-- BACKUP-META {"alembic_revision": "${revision}", "pg_version": "16.4", ` +
      '"created_at": "2026-10-23T12:00:00", "app_version": "0.1.0"}',
    '-- PostgreSQL database dump',
    'COPY public.alembic_version (version_num) FROM stdin;',
    revision,
    '\\.',
    '',
  ].join('\n');
}

function makeSqlFile(content: string, name = 'backup.sql'): File {
  const file = new File([content], name, { type: 'application/sql' });
  vi.spyOn(file, 'text').mockResolvedValue(content);
  return file;
}

async function renderPage() {
  renderWithProviders(<BackupRestore />);
  return screen.findByRole('button', { name: 'Backup wiederherstellen' });
}

async function selectFile(file: File) {
  const input = screen.getByLabelText('Backup-Datei (.sql)');
  await act(async () => {
    fireEvent.change(input, { target: { files: [file] } });
    await Promise.resolve();
  });
}

describe('BackupRestore – restore confirmation flow', () => {
  it('refuses to open the dialog without a selected file', async () => {
    await renderPage();
    fireEvent.click(screen.getByRole('button', { name: /Backup wiederherstellen/i }));
    expect(await screen.findByText('Bitte zuerst eine Backup-Datei auswählen')).toBeInTheDocument();
    expect(screen.queryByText('Wiederherstellung bestätigen')).not.toBeInTheDocument();
  });

  it('shows matching revision for a compatible backup file', async () => {
    await renderPage();
    await selectFile(makeSqlFile(dumpContent(DUMP_REVISION)));
    expect(
      await screen.findByText(/stimmt mit der aktuellen Datenbank überein/),
    ).toBeInTheDocument();
  });

  it('shows a warning when the backup revision differs', async () => {
    backupApi.getInfo.mockResolvedValue({
      ...BACKUP_INFO,
      db_revision: '000000000000',
      head_revision: '000000000000',
    });
    await renderPage();
    await selectFile(makeSqlFile(dumpContent(DUMP_REVISION)));
    expect(
      await screen.findByText(/weicht ab – der Server prüft die Kompatibilität/),
    ).toBeInTheDocument();
  });

  it('requires the checkbox before the destructive button is enabled', async () => {
    await renderPage();
    await selectFile(makeSqlFile(dumpContent(DUMP_REVISION)));
    fireEvent.click(screen.getByRole('button', { name: /Backup wiederherstellen/i }));
    const dialogHeading = await screen.findByText('Wiederherstellung bestätigen');
    expect(dialogHeading).toBeInTheDocument();
    expect(
      screen.getByText(/Durch diese Aktion löschen Sie die alten Daten/),
    ).toBeInTheDocument();
    const replaceButton = screen.getByRole('button', { name: /Datenbank ersetzen/ });
    expect(replaceButton).toBeDisabled();
    fireEvent.click(screen.getByRole('checkbox'));
    expect(replaceButton).toBeEnabled();
  });

  it('calls the restore API and shows the success message', async () => {
    await renderPage();
    await selectFile(makeSqlFile(dumpContent(DUMP_REVISION)));
    fireEvent.click(screen.getByRole('button', { name: /Backup wiederherstellen/i }));
    await screen.findByText('Wiederherstellung bestätigen');
    fireEvent.click(screen.getByRole('checkbox'));
    fireEvent.click(screen.getByRole('button', { name: /Datenbank ersetzen/ }));
    await waitFor(() => expect(backupApi.restore).toHaveBeenCalledTimes(1));
    expect(backupApi.restore.mock.calls[0][0]).toBeInstanceOf(File);
    expect(
      await screen.findByText('Datenbank erfolgreich wiederhergestellt.'),
    ).toBeInTheDocument();
  });

  it('surfaces the German error detail from the server on a conflict', async () => {
    backupApi.restore.mockRejectedValueOnce({
      response: { data: { detail: 'Der Backup wurde mit einer unbekannten Datenbankversion erstellt.' } },
    });
    await renderPage();
    await selectFile(makeSqlFile(dumpContent('ffffffffffff')));
    fireEvent.click(screen.getByRole('button', { name: /Backup wiederherstellen/i }));
    await screen.findByText('Wiederherstellung bestätigen');
    fireEvent.click(screen.getByRole('checkbox'));
    fireEvent.click(screen.getByRole('button', { name: /Datenbank ersetzen/ }));
    expect(
      await screen.findByText('Der Backup wurde mit einer unbekannten Datenbankversion erstellt.'),
    ).toBeInTheDocument();
  });
});
