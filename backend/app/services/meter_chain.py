from fastapi import HTTPException
from sqlalchemy.orm import Session

from .. import models

_MAX_CHAIN_DEPTH = 20


def get_meter_chain(db: Session, meter_id: int) -> list[models.Meter]:
    """Return the meter chain ordered oldest-first.

    Follows replaces_meter_id pointers from the requested meter back to the
    root predecessor. For a single standalone meter, returns [meter].
    For a replacement chain M replaces P replaces G, returns [G, P, M].

    Raises HTTPException 404 if the meter does not exist.
    Limited to _MAX_CHAIN_DEPTH iterations to guard against circular FK data.
    """
    chain: list[models.Meter] = []
    current = db.query(models.Meter).filter(models.Meter.id == meter_id).first()
    if current is None:
        raise HTTPException(status_code=404, detail=f"Meter mit ID {meter_id} nicht gefunden.")

    visited: set[int] = set()
    while current is not None:
        if current.id in visited or len(chain) >= _MAX_CHAIN_DEPTH:
            break
        visited.add(current.id)
        chain.append(current)
        if current.replaces_meter_id is not None:
            current = (
                db.query(models.Meter)
                .filter(models.Meter.id == current.replaces_meter_id)
                .first()
            )
        else:
            break

    # chain is currently [newest, ..., oldest]; reverse to oldest-first
    chain.reverse()
    return chain


def get_full_meter_chain_ids(db: Session, meter_id: int) -> list[int]:
    """Return all meter IDs in the chain (both directions).

    Includes predecessors (via replaces_meter_id) and successors
    (meters whose replaces_meter_id references this meter or any
    chain member). The tariff usage endpoint uses this so that
    readings on a predecessor or successor meter are counted.
    """
    predecessor_chain = get_meter_chain(db, meter_id)
    all_ids: list[int] = [m.id for m in predecessor_chain]
    visited: set[int] = set(all_ids)

    # BFS for successors: any meter whose replaces_meter_id points to
    # a meter already in the chain.
    queue: list[int] = list(all_ids)
    successor_ids: list[int] = []

    while queue and len(successor_ids) < _MAX_CHAIN_DEPTH:
        current_id = queue.pop(0)
        successors = (
            db.query(models.Meter.id)
            .filter(models.Meter.replaces_meter_id == current_id)
            .all()
        )
        for (sid,) in successors:
            if sid not in visited:
                visited.add(sid)
                successor_ids.append(sid)
                queue.append(sid)

    return all_ids + successor_ids