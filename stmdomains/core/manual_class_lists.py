"""Source-bound shared class lists with immutable revisions and display snapshots."""

from dataclasses import replace

from stmdomains.core.analysis_result import FrameAnalysis
from stmdomains.core.manual_classes import ManualClassList
from stmdomains.core.manual_domains import ManualDomains, MANUAL_METHOD


class ManualClassLists:
    def __init__(self) -> None:
        self.current: dict[str, ManualClassList] = {}
        self.revisions: dict[tuple[str, str], ManualClassList] = {}
        self.bindings: dict[str, str] = {}
        self._cache: dict[str, tuple[FrameAnalysis, ManualClassList, FrameAnalysis]] = {}

    @staticmethod
    def source_key(series_id: str, original: FrameAnalysis | None) -> str:
        if original is None:
            return f'{series_id}:without-model'
        if original.catalogue is not None:
            return f'{series_id}:catalogue:{original.catalogue.identifier}'
        # Local results without a fitted catalogue cannot be equated by label/number.
        return f'{series_id}:local-result:{id(original)}'

    def bind(self, variant: ManualDomains) -> None:
        key = self.source_key(variant.data.series_id, variant.original)
        self.bindings[variant.identifier] = key
        if key not in self.current:
            self.publish(ManualClassList.from_result(variant.original, key))

    def get(self, variant: ManualDomains) -> ManualClassList:
        return self.current[self.bindings[variant.identifier]]

    def publish(self, labels: ManualClassList) -> None:
        self.current[labels.source_key] = labels
        self.revisions[labels.identifier, labels.version] = labels
        self._cache.clear()

    def display(self, variant: ManualDomains) -> FrameAnalysis | None:
        base = variant.current if variant.changed else variant.original
        labels = self.get(variant)
        if labels.generation == 0 and (base is None or base.class_list is None):
            return base
        base = base or variant.current
        cached = self._cache.get(variant.identifier)
        if cached is not None and cached[0] is base and cached[1] is labels:
            return cached[2]
        displayed = base if base.class_list is labels else replace(base, class_list=labels,
            parameters={**base.parameters, 'domain_method': MANUAL_METHOD})
        self._cache[variant.identifier] = base, labels, displayed
        return displayed
