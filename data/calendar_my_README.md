# calendar_my.csv: Malaysian public holidays used by onboarding step 1

Loaded when an owner picks **Malaysia** in the setup wizard (`backend/app/modules/setup`). Entries that already
exist in the tenant's calendar (same type, same start date) are skipped, so running it twice adds nothing.

- 2026 holidays are the national dates already used by the synthetic demo data.
- 2027 lists only the **fixed-date** national holidays (1 Jan, 1 May, 31 Aug, 16 Sep, 25 Dec).
- Holidays that follow the moon (Chinese New Year, Hari Raya Aidilfitri/Haji, Awal Muharram, Maulidur Rasul,
  Deepavali, Thaipusam) and **state** holidays (Kedah's Sultan's birthday etc.) must be checked against the
  official government list before a real deployment. Owners can add them on the Calendar page.
- School terms, Ramadan and other periods are NOT loaded here: the owner adds them on the Calendar page
  (optional wizard step 5), because they depend on the restaurant's location.

Synthetic / public-calendar data only; no personal or company records.
