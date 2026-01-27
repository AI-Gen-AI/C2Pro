# ===========================================
# BUDGET-RELATED DOMAIN MODELS
# ===========================================

class BudgetItem(BaseModel):
    """Represents a single item from the project budget."""
    id: UUID
    name: str
    code: str
    amount: float
