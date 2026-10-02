# Kurz
Meeting-Intelligenz auf der eigenen Box — Besprechungen aufnehmen, transkribieren und zusammenfassen, ohne Ton in eine Cloud zu schicken

# Beschreibung
Insilo nimmt Geschäftsbesprechungen auf, transkribiert sie auf der Box und macht daraus strukturierte Protokolle — auf Ihrer eigenen Olares-Box.

**Das Versprechen**
Weder Ton noch Transkript noch Suchindex verlassen die Box. Anders als bei PLAUD, Otter oder Fireflies gibt es keinen Cloud-Upload, keine fremde AI-Schnittstelle und keine Telemetrie.

**Was es kann**
- Aufnehmen im Browser (PWA) oder vorhandene Tonaufnahmen hochladen
- Transkribieren auf der Box mit faster-whisper (large-v3), Sprechertrennung über Stimmprofile
- Strukturierte Zusammenfassungen aus Vorlagen, erstellt von dem Sprachmodell, das Sie angeben
- Fragen an das ganze Besprechungsarchiv (RAG über pgvector)
- Anbindung nach außen: Webhooks mit HMAC-Signatur, REST-API, Markdown-Export — in der Vorgabe nur von Hand ausgelöst

**Datenschutz-Nachweis, gemessen**
Die Navigation zeigt laufend, was die Box tatsächlich verlässt — abgeleitet aus den eingerichteten Endpunkten und den ausgelieferten Bytes im Protokoll, kein Versprechen. Drei Ziele sind möglich, und jedes wird genannt: ein externer Sprachmodell-Endpunkt, eingerichtete Webhooks und der einmalige Modell-Download beim ersten Start.

**Sprachmodell**
Insilo kommt ohne eingerichteten Endpunkt. Tragen Sie unter Einstellungen eine OpenAI-kompatible Adresse ein — zum Beispiel die LiteLLM-App auf derselben Box. Bis dahin funktionieren Aufnahme und Transkription, Zusammenfassungen entfallen, und die App sagt das.

**Gemacht für**
Kanzleien, Steuerberatungen, Unternehmensberatungen und Mittelstand unter DSGVO, BSI-Grundschutz oder Mandatsgeheimnis.

**Oberfläche**
Deutsch, Englisch, Französisch, Spanisch und Italienisch; förmliche Anrede in jeder Sprache. Hell- und Dunkelmodus.

**Ressourcen**
CPU: 4 Kerne angefordert, bis 13
RAM: 12 GB angefordert, bis 24
Speicher: 30 GB (Ton, Whisper- und BGE-M3-Modelle ~3 GB, Datenbankanteil)
GPU: keine — Whisper läuft auf der CPU, das Sprachmodell ist extern
