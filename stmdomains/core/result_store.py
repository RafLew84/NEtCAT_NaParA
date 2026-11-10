"""New results overlay a read-only project without eagerly loading its masks."""

from collections.abc import Iterator, Mapping, MutableMapping

from stmdomains.core.analysis_result import FrameAnalysis


class ResultStore(MutableMapping[int, FrameAnalysis]):
    def __init__(self, saved: Mapping[int, FrameAnalysis]) -> None:
        self.saved = saved
        self.memory: dict[int, FrameAnalysis] = {}
        self.removed: set[int] = set()

    def __getitem__(self, index: int) -> FrameAnalysis:
        if index in self.memory:
            return self.memory[index]
        if index in self.removed:
            raise KeyError(index)
        return self.saved[index]

    def __setitem__(self, index: int, result: FrameAnalysis) -> None:
        self.memory[index] = result
        self.removed.discard(index)

    def __delitem__(self, index: int) -> None:
        if index not in self:
            raise KeyError(index)
        self.memory.pop(index, None)
        self.removed.add(index)

    def __iter__(self) -> Iterator[int]:
        return iter(dict.fromkeys((*self.memory, *(i for i in self.saved if i not in self.removed))))

    def __len__(self) -> int:
        return sum(1 for _ in self)
