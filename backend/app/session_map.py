"""Session Map (PRD 5.3, 7.2): Redis hashes Placeholder <-> original for one Session.

The Redis client must be created with ``decode_responses=True``.
"""

from redis.asyncio import Redis

from app.config import settings
from app.schemas import EntityType

# Atomic claim, KEYS = [fwd, rev, ctr], ARGV = [type, original, ttl_seconds].
# Reverse-lookup first so the same original never burns a second number; all
# three keys share one sliding TTL.
_CLAIM = """
local existing = redis.call('HGET', KEYS[2], ARGV[2])
if existing then
  redis.call('EXPIRE', KEYS[1], tonumber(ARGV[3]))
  redis.call('EXPIRE', KEYS[2], tonumber(ARGV[3]))
  redis.call('EXPIRE', KEYS[3], tonumber(ARGV[3]))
  return existing
end
local n = redis.call('HINCRBY', KEYS[3], ARGV[1], 1)
local ph = '[[' .. ARGV[1] .. '_' .. string.format('%d', n) .. ']]'
redis.call('HSET', KEYS[2], ARGV[2], ph)
redis.call('HSET', KEYS[1], ph, ARGV[2])
redis.call('EXPIRE', KEYS[1], tonumber(ARGV[3]))
redis.call('EXPIRE', KEYS[2], tonumber(ARGV[3]))
redis.call('EXPIRE', KEYS[3], tonumber(ARGV[3]))
return ph
"""


class SessionMap:
    def __init__(self, redis: Redis, sid: str, ttl: int | None = None) -> None:
        self.redis = redis
        self.sid = sid
        self.ttl = settings.session_ttl_seconds if ttl is None else ttl
        base = f"aegis:sess:{sid}"
        self.fwd_key = f"{base}:fwd"
        self.rev_key = f"{base}:rev"
        self.ctr_key = f"{base}:ctr"

    async def get_or_create_placeholder(self, entity_type: EntityType, original: str) -> str:
        """Stable numbering via fwd/rev/ctr (PRD 7.2); sliding TTL refreshed."""
        ph = await self.redis.eval(
            _CLAIM, 3, self.fwd_key, self.rev_key, self.ctr_key,
            entity_type.value, original, self.ttl,
        )
        return str(ph)

    async def resolve(self, placeholder: str) -> str | None:
        """Original for a Placeholder, or None when absent; sliding TTL refreshed."""
        pipe = self.redis.pipeline(transaction=False)
        pipe.hget(self.fwd_key, placeholder)
        pipe.expire(self.fwd_key, self.ttl)
        pipe.expire(self.rev_key, self.ttl)
        pipe.expire(self.ctr_key, self.ttl)
        original, *_ = await pipe.execute()
        return original

    async def forward_map(self) -> dict[str, str]:
        """Every Placeholder -> original of this Session (PRD 5.4); sliding TTL refreshed."""
        pipe = self.redis.pipeline(transaction=False)
        pipe.hgetall(self.fwd_key)
        pipe.expire(self.fwd_key, self.ttl)
        pipe.expire(self.rev_key, self.ttl)
        pipe.expire(self.ctr_key, self.ttl)
        entries, *_ = await pipe.execute()
        return entries
