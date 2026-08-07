// Impressum — verbatim von monoroc.de/impressum.html.
// Wrapper-Klassen kommen aus .legalProse in index.css.

export function ImpressumText() {
  return (
    <div className="legalProse">
      <h3>Impressum</h3>

      <p>
        Christian Modrow
        <br />
        c/o Christian Jahnke
        <br />
        Gulisastraße 93
        <br />
        56072 Koblenz
      </p>

      <h4>Kontakt</h4>
      <p>
        E-Mail: <a href="mailto:cm@monoroc.de">cm@monoroc.de</a>
      </p>

      <h4>Verbraucherstreitbeilegung/Universalschlichtungsstelle</h4>
      <p>
        Wir sind nicht bereit oder verpflichtet, an Streitbeilegungsverfahren vor einer
        Verbraucherschlichtungsstelle teilzunehmen.
      </p>
    </div>
  )
}
