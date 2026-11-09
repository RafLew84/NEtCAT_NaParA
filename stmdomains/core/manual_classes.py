"""Versioned labels for human edits; these never become fitted model classes."""

from dataclasses import dataclass, field, replace
from collections.abc import Collection
import re
from typing import TYPE_CHECKING, Literal
from uuid import uuid4

from stmdomains.core.result_names import class_letter

if TYPE_CHECKING:
    from stmdomains.core.analysis_result import FrameAnalysis


@dataclass(frozen=True)
class ManualClass:
    class_id: str
    name: str
    color: str
    origin: Literal['automatic', 'manual']


@dataclass(frozen=True)
class ManualClassList:
    source_key: str
    catalogue_id: str
    classes: tuple[ManualClass, ...] = ()
    identifier: str = field(default_factory=lambda: uuid4().hex)
    version: str = field(default_factory=lambda: uuid4().hex)
    generation: int = 0

    @classmethod
    def from_result(cls, result: 'FrameAnalysis | None', source_key: str) -> 'ManualClassList':
        return cls(source_key, result.catalogue.identifier if result and result.catalogue else '',
                   tuple(ManualClass(c.class_id, class_letter(i), c.color, 'automatic')
                         for i, c in enumerate(result.classes)) if result else ())

    def edit(self, operation: str, target: str = '', *, name: str = '', color: str = '',
             occupied: Collection[str] = ()) -> 'ManualClassList':
        if operation == 'delete':
            member = next((c for c in self.classes if c.class_id == target), None)
            if member is None or member.origin != 'manual':
                raise ValueError('Usunąć można tylko pustą klasę utworzoną ręcznie.')
            if target in occupied:
                raise ValueError('Klasa ma członków; najpierw usuń ich przypisania we wszystkich wariantach tej listy.')
            return replace(self, classes=tuple(c for c in self.classes if c is not member),
                           version=uuid4().hex, generation=self.generation + 1)
        name = name.strip()
        if not name or len(name) > 80:
            raise ValueError('Nazwa klasy musi mieć od 1 do 80 znaków.')
        if not re.fullmatch(r'#[0-9a-fA-F]{6}', color):
            raise ValueError('Kolor musi mieć postać #RRGGBB.')
        if operation == 'create':
            classes = (*self.classes, ManualClass('manual-' + uuid4().hex, name, color.lower(), 'manual'))
        elif operation == 'update':
            member = next((c for c in self.classes if c.class_id == target), None)
            if member is None:
                raise ValueError('Wybierz klasę z bieżącej listy.')
            if (member.name, member.color) == (name, color.lower()):
                raise ValueError('Nazwa i kolor nie zmieniły się.')
            classes = tuple(replace(c, name=name, color=color.lower()) if c is member else c for c in self.classes)
        else:
            raise ValueError('Nieznana operacja listy klas.')
        return replace(self, classes=classes, version=uuid4().hex, generation=self.generation + 1)
