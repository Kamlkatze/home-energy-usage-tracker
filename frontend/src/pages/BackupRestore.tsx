import React, { useState } from 'react';
import { Button } from '../components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Checkbox } from '../components/ui/checkbox';
import { Dialog } from '../components/ui/dialog';
import { backupApi } from '../api/client';
import { useFetch } from '../hooks/useFetch';
import { BackupInfo, BackupRestoreResult } from '../types';
import {
  AlertTriangle,
  CheckCircle2,
  DatabaseBackup,
  Download,
  Loader2,
  Upload,
} from 'lucide-react';

const META_RE = /-- BACKUP-META (\{.*\})/;
const COPY_REVISION_RE =
  /COPY public\.alembic_version[^\n;]*FROM stdin;\n([^\n]*)/;

function extractDumpRevision(text: string): string | null {
  const metaMatch = META_RE.exec(text);
  if (metaMatch) {
    try {
      const parsed = JSON.parse(metaMatch[1]) as { alembic_revision?: unknown };
      if (typeof parsed.alembic_revision === 'string' && parsed.alembic_revision) {
        return parsed.alembic_revision;
      }
    } catch {
      // fall through to the COPY block below
    }
  }
  const copyMatch = COPY_REVISION_RE.exec(text);
  const value = copyMatch?.[1]?.trim();
  return value ? value : null;
}

function errorDetail(err: unknown, fallback: string): string {
  const detail = (err as { response?: { data?: { detail?: string } } })
    ?.response?.data?.detail;
  return detail ?? fallback;
}

const BackupRestore: React.FC = () => {
  // Bumping reloadKey re-triggers the useFetch effect to refetch after restore.
  const [reloadKey, setReloadKey] = useState(0);
  const {
    data: info,
    loading,
    error: infoError,
  } = useFetch<BackupInfo>(() => backupApi.getInfo(), [reloadKey]);

  const [downloading, setDownloading] = useState(false);
  const [downloadError, setDownloadError] = useState<string | null>(null);
  const [downloadSuccess, setDownloadSuccess] = useState<string | null>(null);

  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [dumpRevision, setDumpRevision] = useState<string | null>(null);
  const [fileError, setFileError] = useState<string | null>(null);

  const [showConfirm, setShowConfirm] = useState(false);
  const [confirmChecked, setConfirmChecked] = useState(false);
  const [restoring, setRestoring] = useState(false);
  const [restoreResult, setRestoreResult] = useState<BackupRestoreResult | null>(null);
  const [restoreError, setRestoreError] = useState<string | null>(null);

  const handleDownload = async () => {
    setDownloading(true);
    setDownloadError(null);
    setDownloadSuccess(null);
    try {
      const { blob, filename } = await backupApi.downloadDump();
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement('a');
      anchor.href = url;
      anchor.download = filename;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      URL.revokeObjectURL(url);
      setDownloadSuccess(filename);
    } catch (err) {
      setDownloadError(errorDetail(err, 'Fehler beim Erstellen des Backups'));
    } finally {
      setDownloading(false);
    }
  };

  const handleFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0] ?? null;
    setSelectedFile(file);
    setDumpRevision(null);
    setFileError(null);
    if (!file) return;
    void file
      .text()
      .then((text) => {
        setDumpRevision(extractDumpRevision(text));
      })
      .catch(() => {
        setFileError('Datei konnte nicht gelesen werden');
      });
  };

  const openConfirm = () => {
    if (!selectedFile) {
      setFileError('Bitte zuerst eine Backup-Datei auswählen');
      return;
    }
    setConfirmChecked(false);
    setRestoreError(null);
    setRestoreResult(null);
    setShowConfirm(true);
  };

  const handleRestore = async () => {
    if (!selectedFile) return;
    setShowConfirm(false);
    setRestoring(true);
    setRestoreError(null);
    setRestoreResult(null);
    try {
      const result = await backupApi.restore(selectedFile);
      setRestoreResult(result);
      setReloadKey((k) => k + 1);
    } catch (err) {
      setRestoreError(errorDetail(err, 'Fehler beim Einspielen des Backups'));
    } finally {
      setRestoring(false);
    }
  };

  const revisionMatches =
    !!info && !!dumpRevision && dumpRevision === info.db_revision;
  const revisionDiffers =
    !!info && !!dumpRevision && dumpRevision !== info.db_revision;

  if (loading) {
    return (
      <div className="p-6">
        <Card>
          <CardContent className="p-8 text-center">
            <Loader2 className="h-8 w-8 animate-spin mx-auto mb-2" />
            <p className="text-muted-foreground">Lade Datenbank-Informationen...</p>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6">
      <Card>
        <CardHeader>
          <CardTitle>Backup &amp; Wiederherstellung</CardTitle>
        </CardHeader>
        <CardContent className="space-y-6">
          {infoError && (
            <div className="text-sm text-destructive bg-destructive/10 p-3 rounded">
              {infoError}
            </div>
          )}

          {/* ---- Current database info ---- */}
          <section className="space-y-2">
            <h2 className="text-lg font-semibold flex items-center gap-2">
              <DatabaseBackup className="h-5 w-5" />
              Aktuelle Datenbank
            </h2>
            <div className="grid sm:grid-cols-2 gap-2 text-sm">
              <div>
                <span className="text-muted-foreground">Alembic-Revision (DB): </span>
                <code className="bg-muted px-1.5 py-0.5 rounded">
                  {info?.db_revision || '–'}
                </code>
              </div>
              <div>
                <span className="text-muted-foreground">Alembic-Revision (Code): </span>
                <code className="bg-muted px-1.5 py-0.5 rounded">
                  {info?.head_revision || '–'}
                </code>
              </div>
              <div>
                <span className="text-muted-foreground">PostgreSQL-Version: </span>
                {info?.pg_version || '–'}
              </div>
              <div>
                <span className="text-muted-foreground">App-Version: </span>
                {info?.app_version || '–'}
              </div>
            </div>
          </section>

          {/* ---- Download ---- */}
          <section className="space-y-2">
            <h2 className="text-lg font-semibold">Backup erstellen</h2>
            <p className="text-sm text-muted-foreground">
              Erstellt einen SQL-Dump der aktuellen Datenbank. Der Dateiname
              enthält Datum und Alembic-Revision, z. B.
              2026-10-23_{info?.head_revision || '…'}_energy_data_backup.sql.
            </p>
            <Button onClick={handleDownload} disabled={downloading}>
              {downloading ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  <span className="ml-2">Erstelle Backup...</span>
                </>
              ) : (
                <>
                  <Download className="h-4 w-4" />
                  <span className="ml-2">Backup herunterladen</span>
                </>
              )}
            </Button>
            {downloadError && (
              <div className="text-sm text-destructive bg-destructive/10 p-3 rounded">
                {downloadError}
              </div>
            )}
            {downloadSuccess && (
              <div className="text-sm text-green-600 dark:text-green-400 flex items-center gap-2">
                <CheckCircle2 className="h-4 w-4" />
                Backup gespeichert als {downloadSuccess}
              </div>
            )}
          </section>

          {/* ---- Restore ---- */}
          <section className="space-y-2">
            <h2 className="text-lg font-semibold">Backup wiederherstellen</h2>
            <p className="text-sm text-muted-foreground">
              Spielt einen zuvor erstellten SQL-Dump ein. Die aktuelle Datenbank
              wird dabei vollständig ersetzt.
            </p>
            <div className="space-y-2">
              <Label htmlFor="backup-file">Backup-Datei (.sql)</Label>
              <Input
                id="backup-file"
                name="backup-file"
                type="file"
                accept=".sql"
                onChange={handleFileChange}
              />
            </div>
            {selectedFile && (
              <div className="text-sm space-y-1">
                <p>
                  <span className="text-muted-foreground">Ausgewählte Datei: </span>
                  {selectedFile.name}
                </p>
                {dumpRevision && (
                  <p className="flex items-center gap-2 flex-wrap">
                    <span className="text-muted-foreground">
                      Backup-Revision:{' '}
                    </span>
                    <code className="bg-muted px-1.5 py-0.5 rounded">
                      {dumpRevision}
                    </code>
                    {revisionMatches && (
                      <span className="text-green-600 dark:text-green-400 flex items-center gap-1">
                        <CheckCircle2 className="h-4 w-4" />
                        stimmt mit der aktuellen Datenbank überein
                      </span>
                    )}
                    {revisionDiffers && (
                      <span className="text-amber-600 dark:text-amber-400 flex items-center gap-1">
                        <AlertTriangle className="h-4 w-4" />
                        weicht ab – der Server prüft die Kompatibilität und
                        migriert bei Bedarf automatisch
                      </span>
                    )}
                  </p>
                )}
                {!dumpRevision && !restoring && (
                  <p className="text-amber-600 dark:text-amber-400">
                    Keine Alembic-Versionsinformation in der Datei gefunden –
                    der Server wird diesen Backup vermutlich ablehnen.
                  </p>
                )}
              </div>
            )}
            {fileError && (
              <div className="text-sm text-destructive bg-destructive/10 p-3 rounded">
                {fileError}
              </div>
            )}
            <Button variant="destructive" onClick={openConfirm} disabled={restoring}>
              {restoring ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  <span className="ml-2">Stelle wieder her...</span>
                </>
              ) : (
                <>
                  <Upload className="h-4 w-4" />
                  <span className="ml-2">Backup wiederherstellen</span>
                </>
              )}
            </Button>
            {restoreResult && (
              <div className="text-sm text-green-600 dark:text-green-400 flex items-center gap-2">
                <CheckCircle2 className="h-4 w-4" />
                {restoreResult.message}
                {restoreResult.upgraded_to && (
                  <span>
                    (Migrationen bis {restoreResult.upgraded_to} angewendet)
                  </span>
                )}
              </div>
            )}
            {restoreError && (
              <div className="text-sm text-destructive bg-destructive/10 p-3 rounded">
                {restoreError}
              </div>
            )}
          </section>
        </CardContent>
      </Card>

      {/* ---- Confirm dialog ---- */}
      <Dialog open={showConfirm} onOpenChange={setShowConfirm}>
        <div className="space-y-4">
          <h2 className="text-lg font-semibold flex items-center gap-2">
            <AlertTriangle className="h-5 w-5 text-destructive" />
            Wiederherstellung bestätigen
          </h2>
          <p className="text-sm">
            Vorsicht: Durch diese Aktion löschen Sie die alten Daten in der
            Datenbank – sie werden vollständig durch den Backup{' '}
            <strong>{selectedFile?.name}</strong>
            {dumpRevision ? (
              <>
                {' '}
                (Revision <code className="bg-muted px-1 rounded">{dumpRevision}</code>)
              </>
            ) : null}{' '}
            ersetzt. Sind Sie sich sicher?
          </p>
          <Label
            htmlFor="restore-confirm"
            className="flex items-start gap-2 text-sm font-normal cursor-pointer"
          >
            <Checkbox
              id="restore-confirm"
              checked={confirmChecked}
              onChange={(event) => setConfirmChecked(event.target.checked)}
            />
            <span>
              Ich verstehe, dass alle aktuellen Daten unwiderruflich ersetzt
              werden. (Ein automatisches Sicherheits-Backup wird vorher erstellt.)
            </span>
          </Label>
          <div className="flex justify-end gap-4 pt-2">
            <Button variant="outline" onClick={() => setShowConfirm(false)}>
              Abbrechen
            </Button>
            <Button
              variant="destructive"
              disabled={!confirmChecked}
              onClick={handleRestore}
            >
              Datenbank ersetzen
            </Button>
          </div>
        </div>
      </Dialog>
    </div>
  );
};

export default BackupRestore;
