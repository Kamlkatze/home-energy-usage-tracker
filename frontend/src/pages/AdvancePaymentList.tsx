import React, { useState, useEffect, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { Button } from '../components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from '../components/ui/table';
import { Dialog } from '../components/ui/dialog';
import { advancePaymentsApi } from '../api/advancePaymentsApi';
import { metersApi } from '../api/client';
import { AdvancePayment, AdvancePaymentCategory, Meter } from '../types';
import { ADVANCE_PAYMENT_CATEGORY_LABELS, ADVANCE_PAYMENT_CATEGORIES, getMeterFieldsForCategory } from '../lib/advancePaymentFields';
import { Loader2, Pencil } from 'lucide-react';

function formatDate(dateStr: string | null): string {
  if (!dateStr) return 'offen';
  const [y, m, d] = dateStr.split('-');
  return `${d}.${m}.${y}`;
}

function getMeterLabel(metersById: Map<number, Meter>, id: number | null): string {
  if (id === null) return '–';
  return metersById.get(id)?.label ?? `Zähler #${id}`;
}

const AdvancePaymentList: React.FC = () => {
  const [advancePayments, setAdvancePayments] = useState<AdvancePayment[]>([]);
  const [meters, setMeters] = useState<Meter[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<AdvancePaymentCategory | null>(null);

  // Edit modal state
  const [editPayment, setEditPayment] = useState<AdvancePayment | null>(null);
  const [editFormData, setEditFormData] = useState<Record<string, string>>({});
  const [editSaving, setEditSaving] = useState(false);
  const [editError, setEditError] = useState<string | null>(null);

  const fetchData = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const [paymentsData, metersData] = await Promise.all([
        advancePaymentsApi.getAll(),
        metersApi.getAll(),
      ]);
      setAdvancePayments(paymentsData);
      setMeters(metersData);
    } catch (err) {
      setError('Fehler beim Laden der Abschlagszahlungen');
      console.error('Error fetching advance payments:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const metersById = new Map(meters.map((m) => [m.id, m]));

  const filteredPayments = advancePayments
    .filter((p) => activeTab === null || p.category === activeTab)
    .sort((a, b) => a.valid_from.localeCompare(b.valid_from));

  // ---- Edit handlers ----
  const openEdit = (payment: AdvancePayment) => {
    setEditPayment(payment);
    setEditFormData({
      valid_from: payment.valid_from,
      valid_to: payment.valid_to ?? '',
      monthly_amount: payment.monthly_amount,
      comment: payment.comment ?? '',
    });
    setEditError(null);
  };

  const handleEditChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target;
    setEditFormData((prev) => ({ ...prev, [name]: value }));
  };

  const handleEditSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editPayment) return;

    if (!editFormData.valid_from || !editFormData.monthly_amount) {
      setEditError('Bitte alle Pflichtfelder ausfüllen');
      return;
    }

    try {
      setEditSaving(true);
      setEditError(null);
      const payload: Record<string, unknown> = {
        valid_from: editFormData.valid_from,
        monthly_amount: editFormData.monthly_amount,
      };
      if (editFormData.valid_to) {
        payload.valid_to = editFormData.valid_to;
      } else {
        payload.valid_to = null;
      }

      payload.comment = editFormData.comment || null;

      await advancePaymentsApi.update(editPayment.id, payload);
      setEditPayment(null);
      await fetchData();
    } catch (err) {
      const detail = (err as { response?: { data?: { detail?: string } } })
        ?.response?.data?.detail;
      setEditError(detail || 'Fehler beim Speichern der Abschlagszahlung');
    } finally {
      setEditSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="p-6">
        <Card>
          <CardContent className="p-8 text-center">
            <Loader2 className="h-8 w-8 animate-spin mx-auto mb-2" />
            <p className="text-muted-foreground">Lade Abschlagszahlungen...</p>
          </CardContent>
        </Card>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-6">
        <Card>
          <CardContent className="p-8 text-center text-destructive">{error}</CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="p-6">
      <Card>
        <CardHeader>
          <CardTitle className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
            <span>Abschlagszahlungen</span>
            <Link to="/advance-payments/new">
              <Button>Neuer Abschlag</Button>
            </Link>
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex gap-2 mb-6 flex-wrap">
            <Button
              variant={activeTab === null ? 'default' : 'outline'}
              size="sm"
              onClick={() => setActiveTab(null)}
            >
              Alle
            </Button>
            {ADVANCE_PAYMENT_CATEGORIES.map((cat) => (
              <Button
                key={cat}
                variant={activeTab === cat ? 'default' : 'outline'}
                size="sm"
                onClick={() => setActiveTab(cat)}
              >
                {ADVANCE_PAYMENT_CATEGORY_LABELS[cat]}
              </Button>
            ))}
          </div>

          {filteredPayments.length === 0 ? (
            activeTab === null ? (
              <div className="text-center py-8 text-muted-foreground">
                <p className="mb-2">Keine Abschlagszahlungen vorhanden.</p>
                <Link to="/advance-payments/new" className="text-primary underline">
                  Neuen Abschlag anlegen
                </Link>
              </div>
            ) : (
              <div className="text-center py-8 text-muted-foreground">
                <p className="mb-2">
                  Keine Abschlagszahlungen für{' '}
                  {ADVANCE_PAYMENT_CATEGORY_LABELS[activeTab]}.
                </p>
                <Link to="/advance-payments/new" className="text-primary underline">
                  Neuen Abschlag anlegen
                </Link>
              </div>
            )
          ) : (
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Zeitraum</TableHead>
                    <TableHead>Zähler</TableHead>
                    <TableHead>Monatlicher Betrag</TableHead>
                    <TableHead>Kommentar</TableHead>
                    <TableHead>Aktionen</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {filteredPayments.map((payment) => {
                    const fields = getMeterFieldsForCategory(payment.category);
                    return (
                      <TableRow key={payment.id}>
                        <TableCell>
                          {formatDate(payment.valid_from)} – {formatDate(payment.valid_to)}
                        </TableCell>
                        <TableCell>
                          {fields.map((f) => {
                            const id = payment[f.name as keyof AdvancePayment] as number | null;
                            return id !== null
                              ? `${f.label}: ${getMeterLabel(metersById, id)}`
                              : `${f.label}: –`;
                          }).join(', ')}
                        </TableCell>
                        <TableCell>{payment.monthly_amount} €</TableCell>
                        <TableCell>{payment.comment || '–'}</TableCell>
                        <TableCell>
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => openEdit(payment)}
                          >
                            <Pencil className="h-4 w-4" />
                          </Button>
                        </TableCell>
                      </TableRow>
                    );
                  })}
                </TableBody>
              </Table>
            </div>
          )}
        </CardContent>
      </Card>

      {/* ---- Edit Modal ---- */}
      <Dialog open={!!editPayment} onOpenChange={(open) => { if (!open) { setEditPayment(null); setEditError(null); } }}>
        {editPayment && (
          <form onSubmit={handleEditSubmit} className="space-y-4">
            <h2 className="text-lg font-semibold">Abschlagszahlung bearbeiten</h2>

            <div className="space-y-1">
              <Label>Kategorie</Label>
              <p className="text-sm">{ADVANCE_PAYMENT_CATEGORY_LABELS[editPayment.category]}</p>
            </div>

            <div className="space-y-1">
              <Label>Zähler</Label>
              <p className="text-sm">
                {getMeterFieldsForCategory(editPayment.category).map((f) => {
                  const id = editPayment[f.name as keyof AdvancePayment] as number | null;
                  return id !== null
                    ? `${f.label}: ${getMeterLabel(metersById, id)}`
                    : `${f.label}: –`;
                }).join(', ')}
              </p>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="edit-valid_from">Gültig ab *</Label>
                <Input
                  id="edit-valid_from"
                  name="valid_from"
                  type="date"
                  required
                  value={editFormData.valid_from}
                  onChange={handleEditChange}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="edit-valid_to">Gültig bis</Label>
                <Input
                  id="edit-valid_to"
                  name="valid_to"
                  type="date"
                  value={editFormData.valid_to}
                  onChange={handleEditChange}
                />
                <p className="text-xs text-muted-foreground">Leer = unbefristet</p>
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="edit-monthly_amount">Monatlicher Betrag (€) *</Label>
              <Input
                id="edit-monthly_amount"
                name="monthly_amount"
                type="number"
                step="0.01"
                required
                value={editFormData.monthly_amount}
                onChange={handleEditChange}
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="edit-comment">Anbieter / Kommentar</Label>
              <Input
                id="edit-comment"
                name="comment"
                type="text"
                value={editFormData.comment}
                onChange={handleEditChange}
                placeholder="z. B. Stadtwerke Musterstadt"
              />
            </div>

            {editError && (
              <div className="text-sm text-destructive bg-destructive/10 p-3 rounded">
                {editError}
              </div>
            )}

            <div className="flex justify-end gap-4 pt-2">
              <Button
                type="button"
                variant="outline"
                onClick={() => { setEditPayment(null); setEditError(null); }}
                disabled={editSaving}
              >
                Abbrechen
              </Button>
              <Button type="submit" disabled={editSaving}>
                {editSaving ? 'Speichern...' : 'Speichern'}
              </Button>
            </div>
          </form>
        )}
      </Dialog>
    </div>
  );
};

export default AdvancePaymentList;