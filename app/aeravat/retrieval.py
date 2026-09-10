KNOWLEDGE = [
 {"title":"Drainage Response SOP","text":"When drainage capacity stress is high, prioritize field inspection of overloaded assets and verify blockage or pump status before operational escalation."},
 {"title":"Water Level Response","text":"When observed water levels rise rapidly, coordinate field verification and localized public safety messaging."},
 {"title":"Traffic Exposure Protocol","text":"For high or critical mapped risk, review exposed roads and activate appropriate traffic-control procedures."},
 {"title":"Data Confidence Protocol","text":"Aeravat must distinguish observed measurements from interpolated or modelled values and communicate confidence when evidence is incomplete."},
]

def retrieve(query: str):
    words = {w.strip(".,?!") for w in query.lower().split() if len(w) > 3}
    return [x for x in KNOWLEDGE if any(w in x["text"].lower() for w in words)][:3]
