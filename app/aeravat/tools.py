from sqlalchemy import desc
from app.db.models import Alert, FieldTeam, SpatialCell, DrainageAsset
from app.services.analytics import all_cells, cell_status
from app.intelligence.drainage import bottlenecks

class AeravatTools:
    def __init__(self, db): self.db = db
    async def current_risk(self): return await all_cells(self.db)
    def nearest_cell(self, lat, lon):
        cells = self.db.query(SpatialCell).limit(5000).all()
        if not cells: return None
        return min(cells, key=lambda c: (c.latitude-lat)**2 + (c.longitude-lon)**2)
    def cell(self, cell_id):
        c = self.db.query(SpatialCell).filter_by(id=cell_id).first()
        return cell_status(self.db, c) if c else None
    def bottlenecks(self):
        assets = self.db.query(DrainageAsset).all()
        rows = [{"id": a.id, "name": a.name, "asset_type": a.asset_type,
                 "latitude": a.latitude, "longitude": a.longitude,
                 "capacity_lps": a.capacity_lps, "current_flow_lps": a.current_flow_lps} for a in assets]
        return bottlenecks(rows)
    def alerts(self):
        return [{"id": a.id, "severity": a.severity, "title": a.title, "message": a.message,
                 "latitude": a.latitude, "longitude": a.longitude}
                for a in self.db.query(Alert).filter_by(acknowledged=False).order_by(desc(Alert.created_at)).limit(50)]
    def teams(self):
        return [{"id": t.id, "name": t.name, "status": t.status,
                 "latitude": t.latitude, "longitude": t.longitude}
                for t in self.db.query(FieldTeam).all()]
