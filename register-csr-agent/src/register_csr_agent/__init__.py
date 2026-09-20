"""register-csr-agent: deterministic CSR/register-map verification package builder.

The public entry points are the Pydantic contracts in :mod:`.models`, the parsing
front ends in :mod:`.parsers`, the deterministic checks in :mod:`.checks`, and the
package builder in :mod:`.pipeline`.

No module in this package performs network I/O. The LLM adapter (:mod:`.llm_adapter`)
is a deterministic mock that only *explains* findings; it never invents access
semantics or signal mappings.
"""

__version__ = "0.1.0"
