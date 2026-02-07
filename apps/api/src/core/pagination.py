from typing import List, TypeVar, Generic, Optional
import base64
import binascii
from pydantic import BaseModel, Field

T = TypeVar('T')

class InvalidCursorException(ValueError):
    """Raised when a cursor is invalid."""
    pass

def encode_cursor(value: str) -> str:
    """Encodes a string value into a base64 cursor."""
    return base64.b64encode(value.encode('utf-8')).decode('utf-8')

def decode_cursor(cursor: str) -> str:
    """Decodes a base64 cursor into a string value."""
    try:
        return base64.b64decode(cursor.encode('utf-8')).decode('utf-8')
    except (binascii.Error, UnicodeDecodeError):
        raise InvalidCursorException("Invalid cursor")

class Page(BaseModel, Generic[T]):
    """
    A generic page model for cursor-based pagination.
    """
    items: List[T] = Field(
        ...,
        description="The list of items on the current page."
    )
    next_cursor: Optional[str] = Field(
        None,
        description="The cursor to use to get the next page of results."
    )
    has_more: bool = Field(
        ...,
        description="Whether there are more pages of results."
    )

async def paginate(
    query,
    model,
    cursor: Optional[str],
    limit: int,
    order_by: str,
    order_direction: str = "desc",
) -> Page[T]:
    """
    Paginates a SQLAlchemy query using a cursor.

    Args:
        query: The SQLAlchemy query to paginate.
        model: The SQLAlchemy model being queried.
        cursor: The cursor from the previous page.
        limit: The number of items to return per page.
        order_by: The column to order the results by.
        order_direction: The direction to order the results by (asc or desc).

    Raises:
        InvalidCursorException: If the provided cursor is invalid.

    Returns:
        A Page object containing the items for the current page and information
        for retrieving the next page.
    """
    if cursor:
        try:
            decoded_cursor = decode_cursor(cursor)
        except InvalidCursorException:
            # Re-raise with a more specific message if needed, or let the caller handle it.
            raise

        # This is a simplified example. In a real-world scenario, you would
        # likely have a more complex cursor format, e.g., "timestamp|uuid".
        # You would then parse this string and apply the WHERE clause accordingly.
        # For simplicity, we assume the cursor is just the value of the ordering column.
        order_column = getattr(model, order_by)
        if order_direction == "desc":
            query = query.where(order_column < decoded_cursor)
        else:
            query = query.where(order_column > decoded_cursor)

    # Fetch one more item than the limit to check if there are more pages.
    items = await query.order_by(
        getattr(model, order_by).desc() if order_direction == "desc" else getattr(model, order_by).asc()
    ).limit(limit + 1).all()

    has_more = len(items) > limit
    items = items[:limit]

    next_cursor = None
    if has_more:
        # The last item in the original list is the first item of the next page.
        # We use its value to create the next cursor.
        last_item = items[-1]
        next_cursor_value = str(getattr(last_item, order_by))
        next_cursor = encode_cursor(next_cursor_value)

    return Page(items=items, next_cursor=next_cursor, has_more=has_more)
