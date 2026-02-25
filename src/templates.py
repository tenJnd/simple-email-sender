from __future__ import annotations

from dataclasses import dataclass
from typing import List


@dataclass
class Template:
    key: str
    subject: str
    body: str


class TemplateRegistry:
    def __init__(self) -> None:
        self._templates = {

            # Default fallback (can be used generally)
            "default": Template(
                key="default",
                subject="Zrychlení práce s výkresy z poptávek",
                body=(
                    "Dobrý den,\n\n"
                    "jsme česká firma zaměřená na automatické zpracování výkresů z poptávek "
                    "ve strojírenství, speciálně obrábění\n\n"
                    "Ve firmách, kde chodí větší množství poptávek e-mailem spolu s technickými "
                    "výkresy (často v PDF nebo rastrové podobě), typicky vidíme desítky hodin "
                    "měsíčně strávených jejich zpracováním.\n\n"
                    "Pomáháme:\n"
                    "– zrychlit práci s výkresy hned po přijetí poptávky\n"
                    "– rychle odfiltrovat nevhodné zakázky\n"
                    "– ušetřit kapacitu techniků i obchodu\n"
                    "– zvládnout vyšší objem poptávek bez navyšování lidí\n\n"
                    "Rychlejší zpracování navíc firmám pomáhá reagovat na poptávky dříve než konkurence "
                    "a mít v rozhodování větší jistotu.\n\n"
                    "Je to něco, co by pro vás mohlo být aktuální?\n\n"
                    "Děkuji\n"
                    "Tomáš\n"
                    "Partonomy / JND labs s.r.o.\n"
                    "partonomy.cz"
                ),
            ),

            # For generic inboxes (info@, obchod@, etc.)
            # Note: key reflects email_type value: "generic"
            "info": Template(
                key="generic",
                subject="Zrychlení práce s výkresy z poptávek",
                body=(
                    "Dobrý den,\n\n"
                    "jsme česká firma zaměřená na automatické zpracování výkresů z poptávek "
                    "ve strojírenství, speciálně obrábění\n\n"
                    "Ve firmách, kde chodí větší množství poptávek e-mailem spolu s technickými "
                    "výkresy (často v PDF nebo rastrové podobě), typicky vidíme desítky hodin "
                    "měsíčně strávených jejich zpracováním.\n\n"
                    "Pomáháme:\n"
                    "– zrychlit práci s výkresy hned po přijetí poptávky\n"
                    "– rychle odfiltrovat nevhodné zakázky\n"
                    "– ušetřit kapacitu techniků i obchodu\n"
                    "– zvládnout vyšší objem poptávek bez navyšování lidí\n\n"
                    "Rychlejší zpracování navíc firmám pomáhá reagovat na poptávky dříve než konkurence "
                    "a mít v rozhodování větší jistotu.\n\n"
                    "Je to něco, co by pro vás mohlo být aktuální? "
                    "Pokud ano, budu rád za nasměrování na správnou osobu.\n\n"
                    "Děkuji\n"
                    "Tomáš\n"
                    "Partonomy / JND labs s.r.o.\n"
                    "partonomy.cz"
                ),
            ),

            # For specific person (technicko-obchodní, vedoucí výroby, atd.)
            # Note: key reflects email_type value: "personal"
            "to_person": Template(
                key="personal",
                subject="Zrychlení práce s výkresy z poptávek",
                body=(
                    "Dobrý den,\n\n"
                    "jsme česká firma zaměřená na automatické zpracování výkresů z poptávek "
                    "ve strojírenství, speciálně obrábění\n\n"
                    "Ve firmách, kde chodí větší množství poptávek e-mailem spolu s technickými "
                    "výkresy (často v PDF nebo rastrové podobě), typicky vidíme desítky hodin "
                    "měsíčně strávených jejich zpracováním.\n\n"
                    "Pomáháme:\n"
                    "– zrychlit práci s výkresy hned po přijetí poptávky\n"
                    "– rychle odfiltrovat nevhodné zakázky\n"
                    "– ušetřit kapacitu techniků i obchodu\n"
                    "– zvládnout vyšší objem poptávek bez navyšování lidí\n\n"
                    "Rychlejší zpracování navíc firmám pomáhá reagovat na poptávky dříve než konkurence "
                    "a mít v rozhodování větší jistotu.\n\n"
                    "Je to něco, co by pro vás mohlo být aktuální?\n\n"
                    "Děkuji\n"
                    "Tomáš\n"
                    "Partonomy / JND labs s.r.o.\n"
                    "partonomy.cz"
                ),
            ),
        }

    def select(self, flags: List[str]) -> Template:
        fset = {f.lower() for f in (flags or [])}
        # Accept both internal flags (to_person/info) and user-facing email_type values (personal/generic)
        if "to_person" in fset or "personal" in fset:
            return self._templates["to_person"]
        if "info" in fset or "generic" in fset:
            return self._templates["info"]
        return self._templates["default"]
