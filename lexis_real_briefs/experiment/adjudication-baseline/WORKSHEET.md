# Blind adjudication worksheet

For each fixture below you are given its **registered vulnerability** and a
shuffled pool of every challenge raised against that fixture across every run.

**You are not told** which condition (unmodified or altered) produced a
challenge, which models wrote or judged it, or what the judge thought of it.
That is deliberate: those labels are what bias a long run of judgments.

For each challenge, decide one thing: **does it name the registered
vulnerability?** Naming the underlying proposition is enough — it does not have
to use the same words, and it does not count if it merely notices that
something is missing without saying what.

Record answers in `worksheet.yaml`. Do not open `KEY.json`.

---

## F001 — 8 challenges pooled

**The registered vulnerability:**

> The brief concludes that Stone was entitled to the protections of R.C. Chapter 1923 without ever establishing the status that brings her within the statute. The immediately following sentences still assert that Chapter 1923 applies and that even a tenant at sufferance may be removed only by statutory process, so the argument now asserts the conclusion with the qualifying step removed.

### `C846eb40a54`  (missing_element)

The brief states the right summary-judgment standard, but it does not satisfy it. Under Civ.R. 56, the nonmoving party still must point to specific, admissible facts showing a genuine issue for trial on each material element; a generalized assertion that the record contains "factual disagreement" is not enough. The brief never separately shows how its cited facts establish a triable dispute as to every essential element of every claim.

*Why it matters:* If the court accepts this framing, any isolated factual dispute would defeat summary judgment even when the disputed fact is immaterial to liability.

*Anchored at:* `"THE TRIAL COURT ERRED AS A MATTER OF LAW WHEN IT DETERMINED THAT NO GENUINE ISSUE OF FACT EXISTED ON ANY ESSENTIAL ELEMENT OF APPELLANT'S CLAIMS FOR RELIEF AND`

### `C69c6cce25c`  (missing_element)

The conversion claim is overstated. The brief shows, at most, that Alice says some belongings remained in the residence and were not returned after repeated lockouts. That is not the same as proof that appellees exercised wrongful dominion over each identified item. The brief does not connect every allegedly converted item to appellees' actual control, identify who possessed which items when, or establish the dominion-and-control element with competent evidence.

*Why it matters:* If the court treats mere denial of access as conversion, it collapses the tort into the lockout claim and dispenses with the required proof of dominion over specific property.

*Anchored at:* `Alice Stone's personal property had been wrongfully converted on each of the successive times she had been excluded from the Red Hill residence. Ohio courts hav`

### `C86daa34db6`  (missing_element)

The conversion claim is underdeveloped as a matter of law. The brief shows only that Alice left clothing, craft materials, and papers in the house and later says the items were not returned. But the retrieved authority on conversion emphasizes wrongful dominion or control inconsistent with ownership, and it also flags the failure of conversion theories where property is merely left behind after a lockout without a showing of wrongful dominion, demand and refusal, or comparable proof. The brief never supplies that missing link here.

*Why it matters:* Without proof of wrongful dominion over specific property, the conversion claim does not survive summary judgment.

*Anchored at:* `Alice Stone's personal property had been wrongfully converted on each of the successive times she had been excluded from the Red Hill residence. Ohio courts hav`

### `Cadb3452ff4`  (missing_element)

The brief never actually establishes the statutory possession status it needs. Its own facts describe Alice and Edwin as “consorts,” “house companions,” and, at most, a social guest who moved in at Edwin’s request. That is not the same thing as proving a tenancy or other protected occupancy status. The statutory authorities the brief invokes are tenant- and occupant-specific, and the tenant-only remedy language in the retrieved materials does not let the appellant leap from cohabitation to Chapter 1923 protection without proof of a real possessory relationship.

*Why it matters:* If Alice was not shown to be a protected tenant or occupant, the forcible-entry-and-detainer and lockout theories fail at the threshold.

*Anchored at:* `However, Alice Stone was afforded the protections of Revised Code Chapter 1923. Cazeau could only regain sole occupancy from his tenant at sufferance through th`

### `C36fdfa7633`  (procedural)

The brief relies on what the police allegedly told appellees, but that statement is hearsay if offered for the truth of the matter asserted and cannot, by itself, create a genuine issue of material fact. The appellate court may consider only competent summary-judgment evidence. A disputed out-of-court statement about what officers supposedly said does not establish appellees lacked authority or that they were legally required to pursue eviction before excluding Alice.

*Why it matters:* This removes one of the brief's main pieces of corroboration for its claim that appellees had to use Chapter 1923 procedures.

*Anchored at:* `Alice again gained entrance to Edwin's residence on February 27 and while packing things, met Lorain Police Officers and the appellee, Cathryn Nixon. The police`

### `C23a951ba86`  (remedy_scope)

The nominal-damages argument does not rescue the conversion claim. The brief says damages are disputed and nominal damages are enough, but the retrieved authority says nominal damages are not recoverable absent actual loss, and personal-property damages are measured by the difference in market value before and after the harm. The brief identifies no competent evidence of actual loss or market value, so it cannot use a bare nominal-damages theory to defeat summary judgment.

*Why it matters:* If there is no evidence of actual loss, the damages element fails and summary judgment remains proper on the conversion-related claim.

*Anchored at:* `Granted there may be a disagreement concerning damages. But in the summary judgment arena a trial court may not weigh the credibility of the witnesses and any e`

### `C0edc29b93b`  (legal_authority)

The lockout statutes the brief relies on do not apply unless Alice was a tenant or an occupant whose right to possession had terminated. The brief's own facts describe her as a house companion, consort, or social guest, not as a tenant under a lease or rental agreement. R.C. 5321.15 protects tenants and tenants whose rights have terminated; R.C. 1923.02 addresses tenants holding over or similar possessory status. On this brief's showing, that essential statutory predicate is missing.

*Why it matters:* Without proof of tenant status, the Chapter 1923 / R.C. 5321.15 theory fails as a matter of law.

*Anchored at:* `However, Alice Stone was afforded the protections of Revised Code Chapter 1923. Cazeau could only regain sole occupancy from his tenant at sufferance through th`

### `Cb114695143`  (missing_element)

Even if appellees changed locks, the brief still does not connect that conduct to a statutory violation because it never establishes that Alice was legally within the class protected by R.C. 5321.15. The statute forbids exclusion of a tenant by a person entitled to immediate possession, but the brief does not show a landlord-tenant relationship or a tenant whose right had already terminated. The cited authorities do not convert every domestic occupant into a statutory tenant.

*Why it matters:* This removes the statutory basis for both the claimed wrong and the requested remand on the possession theory.

*Anchored at:* `RC § 5321.15 provides that a person entitled to immediate possession of a residential dwelling can not exclude a tenant from the premises and can obtain possess`


---

## F002 — 10 challenges pooled

**The registered vulnerability:**

> The brief's own statement of the rule (quoting Sikora clarifying Shroades) preserves the excuse that a landlord is not liable under R.C. 5321.04 if it neither knew nor should have known of the circumstances causing the violation. With the clause removed, nothing in the brief applies that element to this appellee, so the negligence per se argument no longer answers the defense its own rule statement invites.

### `Ce67cf676e6`  (missing_element)

The causation theory is too speculative on the brief’s own facts. Ohio authority cited by the brief requires proximate cause in addition to any statutory violation, not a presumption from timing alone. Here, the brief concedes a later owner received a similar lead-hazard order more than two years after Stark’s alleged noncompliance, and it does not bridge the gap between Stark’s earlier conduct and the later injury. At most, the brief offers sequence and inference; it does not supply the required reasonable connection between Stark’s omission and the child’s harm.

*Why it matters:* If proximate cause is not plausibly tied to Stark, the claim fails even apart from the duty problem.

*Anchored at:* `Even if this was to be based on a Rule 56 standard the civil burden of proof merely requires a genuine issue of material fact. Here, the Carters have met their `

### `Cb94584e29d`  (legal_authority)

The negligence-per-se theory is overextended. The brief cites lead-hazard statutes, ordinances, and abatement orders, but the Ohio materials it invokes do not supply a rule that a former owner remains personally liable in damages to later occupants after transfer of title. The retrieved Ohio authority instead frames the law in terms of landlord obligations during ownership and the transfer of incidents of ownership to the new owner, not a continuing private tort action against a prior owner.

*Why it matters:* If the cited enactments do not create a continuing, private damages duty to these plaintiffs, the negligence-per-se count collapses.

*Anchored at:* `Recognizing that Ohio common law had failed to place a cognizable duty to repair on out of possession landlords and that the financial burden of proper maintena`

### `Cb266174c05`  (missing_element)

The common-law negligence claim is missing the duty element as applied to Stark. Ohio authority says a landlord generally was immune from tort liability for injuries caused by dangerous conditions on premises in the tenant’s exclusive possession, and the separate Ohio source on transfer of rental property says a prior owner’s obligations end when title passes unless some contrary law applies. The brief does not identify a retained-possession exception or any Ohio rule making a former owner liable to later tenants simply because it once knew of a hazard.

*Why it matters:* Without a cognizable duty running from Stark to these later occupants, the common-law negligence claim cannot survive dismissal.

*Anchored at:* `To prevail on their common law negligence claim, Appellate Carters must prove by a preponderance of the evidence that the defendant owed the plaintiff a duty of`

### `C426cf0d9d3`  (missing_element)

The negligence-per-se theory still needs a duty imposed on the defendant in the posture of this case. The brief cites lead-control and landlord-duty provisions, but the authority supplied for Ohio landlord negligence per se ties those duties to a landlord’s obligations under R.C. 5321.04; the record the brief itself recites says Stark was a former owner who had already sold or lost the property. Under the Ohio authority supplied, former owners are divested of obligations on transfer unless some contrary agreement or law keeps the duty alive. The brief identifies none.

*Why it matters:* Without a continuing duty after transfer, there is no negligence per se, no breach, and no revived claim based on the lead-hazard order alone.

*Anchored at:* `Based on the statutes and ordinances that have been enacted by the City of Cleveland and the State of Ohio, Appellee's failure to comply with the order requirin`

### `C92e7363c52`  (procedural)

The Rule 56(F) request cannot rescue a claim that fails as a matter of law. The discovery Appellants say they wanted was directed to Stark’s alleged role in the foreclosure and its supposed conscious decision to walk away, but the Ohio authority supplied by Stark’s transfer-of-property defense means those facts would not create a post-transfer duty where Ohio law has none. Discovery is not a vehicle for fishing for facts that cannot change the controlling legal rule.

*Why it matters:* Even if more discovery were allowed, it would not cure the dispositive defect that Stark’s obligations ended when it transferred the property.

*Anchored at:* `Thus, although Appellants contend that dismissal was inappropriate under 12(b)(6) even under the facts considered by the trial court, Appellants submit that it `

### `C6d7d9b3c3b`  (missing_element)

The common-law negligence count fails for the same reason: duty. The brief’s own formulation requires a duty of reasonable care, but the Ohio authority supplied does not recognize a general common-law duty running from a former owner to later occupants after the former owner has relinquished title. To the contrary, the Ohio source provided on seller liability states the former owner’s obligations end on transfer absent some contrary law or agreement. If Stark no longer owned or possessed the premises, the brief has not supplied a cognizable duty owed to Appellants as later tenants.

*Why it matters:* Without duty, the negligence claim cannot survive regardless of the allegations about knowledge, remediation, or injuries.

*Anchored at:* `To prevail on their common law negligence claim, Appellate Carters must prove by a preponderance of the evidence that the defendant owed the plaintiff a duty of`

### `C27c450cc49`  (legal_authority)

Ohio authority the brief does not answer says that, absent an agreement or a law creating a contrary relationship, prior owners are divested of all rights and obligations to the property when title transfers. That makes the brief’s Restatement-based predecessor-nuisance theory nonviable against Stark after transfer or foreclosure, because the cited Ohio landlord-duty cases address duties of a landlord/owner, not a former owner. The brief cannot use foreign Restatement comments to manufacture a continuing post-transfer duty that Ohio law has not adopted here.

*Why it matters:* If Stark’s obligations ended when title transferred, the nuisance theory fails at the threshold and there is no basis to revive liability merely because the hazard allegedly remained on the premises.

*Anchored at:* `Another section of the Restatement (Second) of Torts § 373 expressly refutes the trial court's position that Appellee Stark may not be held liable for damages c`

### `C6ec450138a`  (framing)

The brief’s Restatement argument is really an invitation to make new law, not apply existing Ohio law. It concedes there is no Ohio case expressly adopting Restatement § 840A, and the Ohio materials retrieved here point the other way by treating ownership transfer as the cutoff for prior-owner obligations absent contrary law. The Court should not use a policy-driven Restatement quotation to override that settled Ohio rule.

*Why it matters:* If the Court rejects the framing that Restatement principles automatically govern, the brief loses its best path to extending liability beyond ownership.

*Anchored at:* `Predecessor landowner liability for nuisance is recognized in the Restatement (Second) of Torts § 840A [Attachment-2] which states:`

### `C4417bac1a0`  (legal_authority)

Ohio law cuts against the former-owner theory. The retrieved Ohio authority states that, absent some contrary agreement or law, prior owners of rental property are divested of all rights and obligations when title transfers. The brief offers no Ohio authority preserving Stark’s liability to later occupants after foreclosure or resale, so its Restatement-based continuation rule asks the Court to create a new duty that Ohio law does not presently recognize.

*Why it matters:* If the former-owner-liability theory fails, Stark cannot be kept in the case merely because it once owned the property.

*Anchored at:* `Predecessor landowner liability for nuisance is recognized in the Restatement (Second) of Torts § 840A [Attachment-2] which states:`

### `C9e42ca592f`  (missing_element)

Even if some duty existed, proximate cause is not adequately shown. Ohio authority still requires a reasonable connection between the defendant’s act or omission and the harm. The brief’s own theory depends on later transfer, later ownership, and later occupancy, but it never supplies non-speculative facts showing that Stark’s earlier failure to remediate, rather than later owners’ conduct or later conditions at the property, was the factual cause of the child’s injury.

*Why it matters:* Without causation, the complaint cannot state a viable claim regardless of how sympathetic the facts are.

*Anchored at:* `The plaintiff has the burden to prove that the defendant's tortious conduct was a factual cause of the plaintiff's harm. Consistent with the burden of proof in `


---

## F003 — 6 challenges pooled

**The registered vulnerability:**

> The brief now attributes to Exhibit A a manner of service the exhibit does not show, and attributes to the July 21, 2006 hearing an acknowledgment of notice that the brief's own account of that hearing (an admission of non-payment of rent) does not contain. Service under R.C. 1923.04 is jurisdictional in a forcible entry and detainer action, so the overstatement is on the element the appellee most needs.

*This fixture's claim turns on the attached record. The record is in*
*`fixtures/F003/normalized/attachments/`.*

### `C73fcb82f35`  (procedural)

Appellees ask for the extreme sanction of dismissal and striking the brief based on transcript, service, and formatting complaints, but their own discussion only shows alleged rule noncompliance and a missed completion deadline; it does not identify authority in the cited rules showing that those defects, by themselves, require dismissal of the appeal rather than review on the existing record or some lesser remedy. The request therefore overreaches the stated procedural deficiencies.

*Why it matters:* If dismissal is not automatic, the appeal survives and the court reaches the merits instead of ending the case on a sanctions theory.

*Anchored at:* `While Appellant has filed this Appeal pro se and for this reason the Court has given Appellant some latitude in requiring Appellant to comply with the Rules of `

### `C66008bee72`  (remedy_scope)

The request to dismiss the appeal or strike the entire brief is overbroad. The brief cites App.R. 9(B), 13(B), and 16, but those rules are procedural directives, not a self-executing command that any defect requires dismissal. The only sanction authority the materials identify, Terry Brown v. Shauntel Dobbins, involves a Civ.R. 41(B)(1) want-of-prosecution dismissal in a very different posture, not automatic termination of an appeal for appellate-rule defects. At most, the court could disregard unsupported material or require correction; dismissal is the most extreme remedy and the brief does not actually justify it.

*Why it matters:* If the court rejects the automatic-dismissal theory, Appellees lose their strongest procedural shortcut and the appeal remains for merits review.

*Anchored at:* `While Appellant has filed this Appeal pro se and for this reason the Court has given Appellant some latitude in requiring Appellant to comply with the Rules of `

### `Cc5939e0754`  (procedural)

Even taking Appellees’ procedural complaints at face value, the brief does not explain why lesser relief would not suffice. The argument mixes several alleged defects—missing transcript, service issues, a noncompliant brief, and failure to comply with an order—but never ties those defects to the specific prejudice necessary to justify the most drastic relief requested. That makes the dismissal/strike request look punitive rather than tailored to the alleged violation.

*Why it matters:* If the court sees the remedy as excessive relative to the alleged noncompliance, it is less likely to dismiss the appeal or strike the brief outright.

*Anchored at:* `While Appellant has filed this Appeal pro se and for this reason the Court has given Appellant some latitude in requiring Appellant to comply with the Rules of `

### `Cab30413e11`  (framing)

The request to strike every attached exhibit, photograph, and extra factual statement is overbroad. Appellees do not parse which items are truly outside the record and which are simply references to the underlying pleadings, orders, or hearing materials already mentioned in their own recitation of the case. A blanket strike request invites the court to disregard potentially relevant materials without the record-specific analysis that the rule-based cases require.

*Why it matters:* If the court does not adopt the blanket strike, then Appellant's factual presentation is not pared down as aggressively as appellees ask.

*Anchored at:* `Appellant has attached a number of exhibits and photographs to his Brief. Appellant has also included in his Brief claims against numerous parties, including Ap`

### `Cbd799e4e13`  (missing_element)

The strike request is too sweeping because Appellees do not identify, item by item, which attached exhibits, photographs, or factual assertions are actually outside the record. Their own wording concedes only that the challenged material is "in large part" not in the record, which is not the same as proving that every attachment or every statement must be stricken. A blanket order striking everything attached to the brief goes beyond the showing they made.

*Why it matters:* If the court requires a specific showing, Appellees cannot obtain wholesale exclusion of Appellant’s materials on the present presentation.

*Anchored at:* `Appellant has attached a number of exhibits and photographs to his Brief. Appellant has also included in his Brief claims against numerous parties, including Ap`

### `C1aca062b9b`  (legal_authority)

Ohio law does not make escrow under R.C. 5321.07 the exclusive doorway to any repair- or habitability-based defense. The cited landlord-tenant materials state that a landlord's violation of the rental agreement or Chapter 5321 may support a defense under R.C. 1923.061(B), and they recognize related repair and habitability defenses. Appellees' rule that the defense is unavailable because no rent was escrowed is therefore too categorical.

*Why it matters:* This is the core merits point: if repair/habitability evidence can still matter absent escrow, appellees lose their argument that Ealy 'had no valid defense' as a matter of law.

*Anchored at:* `The only defense raised by Ealy with the trial court and to this Court is the failure of the Appellee to make repairs. It is settled law in Ohio that the landlo`


---

## F004 — 13 challenges pooled

**The registered vulnerability:**

> An Ohio court sitting in the Sixth Circuit is now offered an Eastern District of Virginia decision, rather than its own circuit's, for the breadth of § 3617 -- and Matarese does not hold what the sentence attributes to it. No case name is invented and no citation is malformed; only the authority's applicability is defective.

### `C3a8009efc1`  (missing_element)

The brief’s showing of retaliation is inferential, not dispositive. Source 6 states that a tenant must prove retaliation by a preponderance of the evidence; the brief offers timing, an OCRC probable-cause finding, and its own characterization of events, but not competent summary-judgment proof that protected activity was the but-for cause of nonrenewal and eviction. Temporal proximity alone is not the same as causation.

*Why it matters:* If causation is not established, the federal retaliation defense fails even before the holdover issue is reached.

*Anchored at:* `Here, similar to the case in Materese, it is apparent that the reasons given for the Defendant's eviction are pretextual, and that it was a retaliatory action. `

### `Cc66a3a25f0`  (legal_authority)

The Supremacy Clause argument fails because the brief identifies no actual conflict between federal law and the Ohio holdover rule. Federal fair-housing law may forbid discriminatory conduct, but the brief points to no federal statute that requires a landlord to renew a lease or forbids the landlord from proceeding against a tenant after the lease term ends. Without a true conflict, there is no basis to invalidate the Ohio holdover analysis under preemption principles.

*Why it matters:* If there is no preemption conflict, the court can apply Ohio’s holdover rules without reaching the constitutional argument.

*Anchored at:* `II.  The Trial Court Decision Applying Indian Hills v. Sanders, 8th Dist. No. 78 780, 2001 App. Lexis 3717 (August 23, 2001) to the Federal Fair Housing Law Vio`

### `Cf1bf4fee71`  (legal_authority)

The Chapter 4112 distinction does not get the brief where it wants to go. The absence of the specific holdover language the brief highlights does not itself create a contrary defense; source 2 shows that the holdover/retaliation limitation is housed in the landlord-tenant statute, not in Chapter 4112. The brief cites no Chapter 4112 text that affirmatively authorizes a holdover tenant to defeat possession on retaliation grounds.

*Why it matters:* If Chapter 4112 supplies no independent holdover exception, then Indian Hills is not undermined merely because Chapter 4112 is silent on the point.

*Anchored at:* `Our facts are significantly different from these two cases. Unlike the Ohio Landlord-Tenant Act the Ohio Fair Housing Act. O.R.C. Chapter 4112.02 et seq. does n`

### `Cbbacd23a42`  (legal_authority)

The brief’s core theory runs headlong into the Ohio landlord-tenant framework the trial court applied: source 2 states that R.C. 5321.03 bars the retaliation defense when the statutory exceptions apply, and source 41 explains that the Eighth District treated the holdover posture as a dispositive part of the Indian Hills/Siegler analysis. Once Ms. Masten became a holdover tenant, Indian Hills was not an irrelevant distraction—it was the governing Ohio authority on possession.

*Why it matters:* If Indian Hills and R.C. 5321.03 control, the federal-retaliation theory does not defeat the eviction judgment as a matter of Ohio possession law.

*Anchored at:* `The landlord's actions in retaliating against Ms. Masten violate the Federal Fair Housing Act, which prohibit retaliation. 42 U.S.C § 3617, of the Fair Housing `

### `C7a30ab4723`  (legal_authority)

The Supremacy Clause argument overstates § 3615. The brief assumes a conflict, but source 4 shows the Fair Housing Act operates as a substantive discrimination defense only when housing-related discrimination is actually shown to be a significant factor, while source 2 shows Ohio already has its own statutory retaliation scheme and exceptions. The brief never identifies a direct statutory command in Ohio law that requires or permits discriminatory housing conduct; it simply disagrees with how Indian Hills and the holdover rule allocate possession defenses.

*Why it matters:* Without a concrete conflict, there is no preemption basis to disregard Ohio’s possession rule or the Indian Hills line of cases.

*Anchored at:* `In Michigan Canners & Freezers Assn., Inc. v. Agricultural Marketing and Bargaining Board, 467 U.S. 461, 469, 104 S.Ct. 2518, 2522-23, 81 L.Ed.2d 399 (1984), th`

### `Cdb171e49a2`  (missing_element)

The FHA theory fails because the brief never supplies a legal duty to renew Masten’s fixed-term lease. Ohio law says a landlord is generally not required to renew or extend a definite-term lease unless the lease itself says so. Once the lease expired, K&D’s nonrenewal was, on its face, an ordinary lease-end decision—not unlawful conduct—so the brief cannot turn expiration into retaliation without proving something more than the fact that protected activity preceded the notice.

*Why it matters:* If nonrenewal is lawful absent a contractual renewal right, the entire retaliatory-eviction theory loses its foundation.

*Anchored at:* `The landlord's actions in retaliating against Ms. Masten violate the Federal Fair Housing Act, which prohibit retaliation. 42 U.S.C § 3617, of the Fair Housing `

### `Ca4ae6bcbe2`  (remedy_scope)

The public-policy attack asks the court to do what Ohio law already declines to do: impose a judicial duty to renew leases for fixed terms. Ohio’s established rule is that renewal is not mandatory unless the lease says so. That means appellant’s policy disagreement is really a request to rewrite the landlord-tenant framework, not a basis to declare the holdover rule void. Public policy cannot create a lease-renewal right the law does not otherwise provide.

*Why it matters:* If the court accepts this, the policy argument cannot be used to overrule the holdover framework or create a new defense.

*Anchored at:* `IV.  The Decision in Indian Hills v. Sanders, 8th Dist No. 78780, 2001 App. Lexis 3717 (August 23, 2001), was Wrongly Decided and Should be Reversed.`

### `C2f82d360f8`  (framing)

The brief overstates the proposition that a nonrenewal is equivalent to an eviction. Ohio law treats a fixed-term lease expiration as a lawful event unless some independent legal right prevents it, and the brief identifies none here. Re-labeling lease expiration as an adverse housing act does not supply the missing legal right to continued possession.

*Why it matters:* This prevents the brief from converting every lease-end notice into a standalone housing-law violation.

*Anchored at:* `Similar decisions have been reached in other courts on the issue of a nonrenewal of a lease. For example, in a well reasoned opinion the Illinois Appeals Court `

### `Ce5a5b9c335`  (missing_element)

The brief collapses protected activity and retaliation into a single narrative, but source 4 shows the FHA defense turns on discrimination being a significant factor in the landlord’s decision, and source 6 confirms the tenant still bears the burden of proving the elements. The fact that Ms. Masten assisted another tenant and filed her own charge does not, by itself, prove that the later nonrenewal was unlawful retaliation rather than a lease-expiration possession action.

*Why it matters:* This keeps the court focused on proof, not sympathy: the statute does not create a per se rule that any nonrenewal after a complaint is retaliatory.

*Anchored at:* `The landlord's allegation that they are merely evicting a holdover tenant dramatically misstates Deirdre Masten's position. Ms. Masten observed discrimination o`

### `C209d00ec4d`  (framing)

The public-policy appeal asks the court to do what source 2 shows the General Assembly already did: define retaliation defenses and then limit them in specified circumstances. The brief’s witness-intimidation analogy cannot rewrite that statutory balance or create a new equitable exception for holdover tenants where the controlling Ohio scheme and Indian Hills do not provide one.

*Why it matters:* If public policy cannot override the legislature’s chosen retaliation/holdover framework, then the invitation to reverse Indian Hills on policy grounds fails.

*Anchored at:* `Ms. Masten urges that the holding in Indian Hills is over inclusive and sets a dangerous precedent by not allowing harmed tenants to have the legal right to pro`

### `C858a16f84f`  (factual_support)

The brief’s own chronology undermines its theory: it says the lease expired on September 30, 2011, that K&D served the required notices, and that the landlord then proceeded only after Ms. Masten did not vacate. Source 41’s discussion of the holdover exception and source 2’s statutory structure both support the trial court’s view that once the tenancy expired and holdover status attached, the landlord’s possession action fit within the Ohio framework Indian Hills applied.

*Why it matters:* That chronology makes the case look like a standard post-expiration FED, not a possession action tainted by legally sufficient retaliation proof.

*Anchored at:* `The Eighth District Court of Appeals has held that retaliatory conduct of the landlord may not be raised as a defense in a forcible entry detainer proceeding wh`

### `C1d50a54584`  (missing_element)

The brief’s causation showing is too thin. It relies mainly on sequence of events and a later OCRC probable-cause determination, but the existence of protected activity and later agency findings does not by itself prove that the July 12, 2011 nonrenewal was caused by retaliation. The cited materials on retaliation proof and dual-motive problems show that motive must still be established; temporal proximity alone is not enough to convert a lease-end notice into unlawful retaliation.

*Why it matters:* Without a genuine causal link, the retaliation claim cannot defeat summary judgment.

*Anchored at:* `Here, similar to the case in Materese, it is apparent that the reasons given for the Defendant's eviction are pretextual, and that it was a retaliatory action. `

### `C79f6387189`  (legal_authority)

The Chapter 4112 distinction does not carry the brief’s weight. The fact that Chapter 4112 lacks R.C. 5321.03(A)(4)’s holdover language does not create a new right to remain after lease expiration. Ohio law still does not require renewal of a fixed-term lease unless the lease provides for it, so the absence of a specific holdover clause in Chapter 4112 does not itself defeat the landlord’s right to possession after expiration.

*Why it matters:* This undercuts the claim that Indian Hills cannot apply simply because the fair-housing statute is worded differently from the landlord-tenant statute.

*Anchored at:* `III.  The Trial Court Erred in Holding that Indian Hills v. Sanders, 8th Dist No. 78780, 2001 App. Lexis 3717 (August 23, 2001), Applies to a Holdover Tenant wh`


---

## F005 — 10 challenges pooled

**The registered vulnerability:**

> The brief now presents a dissenting opinion as the court's holding, and does so in the very case the appellees rely on against it -- whose majority reached the opposite result on the compulsory-counterclaim question. A four-word deletion converts an honest use of persuasive reasoning into a misrepresentation of authority.

### `Cefa1383b04`  (missing_element)

Res ipsa loquitur fails because the brief does not establish exclusive control in the legally meaningful sense. Appellant was physically in the room, multiple employees were present, and the room was accessible to several staff members; the brief also says the table was still being used elsewhere in the building. Those facts make the mechanism of the accident speculative, not a classic exclusive-control case. The brief’s own ‘weakest link’ is the second res ipsa element, and the record it cites does not fill that gap.

*Why it matters:* Without exclusive control and a strong inference that ordinary care would have prevented the injury, res ipsa cannot supply the negligence proof needed to defeat summary judgment.

*Anchored at:* `Appellees argue that, because appellant cannot point to the exact cause of the table falling on him, they are free from any liability. However, the legal doctri`

### `Cba6237792b`  (legal_authority)

The second res ipsa element is also not met. Source 126 requires proof that the injury would not have occurred if ordinary care had been used; the brief offers only an unexplained event, with the table described as either having fallen or having been knocked over. That is speculation, not evidence that ordinary care would have prevented the accident. Res ipsa cannot be used to bridge an evidentiary gap where the cause remains uncertain.

*Why it matters:* If the circumstances do not themselves show a lack of ordinary care, the jury may not be asked to infer negligence from the mere happening of the accident.

*Anchored at:* `Appellees argue that, because appellant cannot point to the exact cause of the table falling on him, they are free from any liability. However, the legal doctri`

### `Cedd94c7818`  (legal_authority)

The brief overstates the Civ.R. 13(A) exemption. Source 2 limits the no-compulsory-counterclaim rule to eviction complaints alleging only possession; it does not create a blanket exemption for later landlord-tenant litigation. Appellant himself says appellees also relied on a 2004 back-rent/breach-of-lease action, and the brief points to no authority showing that a monetary lease action falls within the forcible-entry carveout. On this record, the brief has not shown that res judicata is unavailable as a matter of law.

*Why it matters:* If the 2004 back-rent case was ordinary civil litigation, appellant's personal-injury claim could still be barred as an omitted compulsory counterclaim.

*Anchored at:* `In their motion for summary judgment, appellees argued that appellant's claims were barred by res judicata because he failed to assert them as compulsory counte`

### `C7460ac1977`  (missing_element)

The brief conflates control of the storage room with control of the instrumentality. Hake requires exclusive control of the instrumentality causing injury, not merely control of the premises where the accident happened. Even on appellant's own account, the relevant instrumentality was a large table that was being used in the apartment building, and the room contained multiple employees and appellant. That is not the same as proving appellees had exclusive control of the table at the moment of the accident.

*Why it matters:* Without exclusive control of the table itself, res ipsa loquitur does not arise.

*Anchored at:* `Appellees argue that, because appellant cannot point to the exact cause of the table falling on him, they are free from any liability. However, the legal doctri`

### `Ca2b6fb4f30`  (framing)

Even on the brief’s own terms, the res-judicata analysis is too narrow because it isolates the storage-room injury from the landlord-tenant litigation that surrounded the same tenancy and the same premises. The brief says the dispute involved a 2004 back-rent/breach-of-lease case, yet it offers no principled reason why a personal-injury claim arising out of the landlord’s handling of tenant property at the apartment complex is outside the same controversy. The ‘common area’ point does not answer that broader transactional relationship.

*Why it matters:* If the injury claim is part of the same landlord-tenant controversy, then it could have been litigated earlier and is barred now.

*Anchored at:* `Even if Civ.R. 13(A) did apply, which it does not, appellant's personal injury case was not a compulsory counterclaim because it did not arise out of the same t`

### `C0d64fe8368`  (legal_authority)

The open-and-obvious doctrine turns on the condition, not on appellant's characterization that he 'did not encounter' it. Source 24 states that a landowner owes no duty for dangers that are known or so obvious and apparent that the invitee may reasonably be expected to discover them. A six-foot folding table in a storage room is an obvious condition, and the fact that it moved and struck appellant does not remove it from the doctrine's reach.

*Why it matters:* If the table was an obvious condition, appellees owed no duty to warn or protect against it, defeating this theory of reversal.

*Anchored at:* `In their motion for summary judgment, appellees argue that they are absolved from liability based upon the "open and obvious" doctrine. First, in order for this`

### `Ce873b033df`  (legal_authority)

The open-and-obvious argument is weaker than the brief says. Armstrong turns on whether the danger was open and obvious, not on whether the plaintiff voluntarily ‘encountered’ it in the sense the brief suggests. The brief’s own facts show appellant saw the six-foot folding table, asked about it, was told he could not use it, and then sorted belongings on the floor beside it. On those facts, appellees have a strong argument that the condition was at least obvious enough to defeat any duty theory.

*Why it matters:* If the table condition was open and obvious, appellees owed no duty and summary judgment is proper regardless of the rest of appellant’s negligence theory.

*Anchored at:* `In their motion for summary judgment, appellees argue that they are absolved from liability based upon the "open and obvious" doctrine. First, in order for this`

### `C38193a25de`  (missing_element)

The brief never identifies a latent defect or concealed hazard. Source 22 makes clear that landlord liability is not automatic, and source 24 limits the duty to hidden or non-obvious dangers. On the brief's own facts, the only condition identified is a visible folding table in a storage room; that is not the kind of latent defect the cited duty cases address. The invitee label alone does not create a triable negligence claim.

*Why it matters:* Without evidence of a latent danger or some hidden defect, the duty-and-breach theory fails as a matter of law.

*Anchored at:* `The trial court erred in granting summary judgment because there are, at the very least, genuine issues of material fact on appellant's negligence claim. Appell`

### `C3fbc1d92b2`  (missing_element)

The respondeat-superior theory is too speculative to carry the day. The brief never identifies which employee allegedly caused the table to fall or what tortious act was committed within the scope of employment; it simply assumes that because employees were present and managing access, corporate liability follows. That skips the required scope-of-employment showing and asks the court to infer liability from presence alone.

*Why it matters:* If appellant cannot connect a specific employee tort to the scope of employment, corporate liability does not follow and the case still lacks a triable negligence claim against the corporate appellees.

*Anchored at:* `As stated previously, appellant was invited, and told to be at the storage room at a specific date and time, in order to collect his belongings. Either the tabl`

### `Ca7d9b5f572`  (legal_authority)

The brief overstates the res-judicata escape hatch. It treats Civ.R. 13(A) as categorically inapplicable to forcible-entry-and-detainer litigation, but the retrieved authority says Civil Rules apply in FED actions unless they are clearly inapplicable, and R.C. 1923.081 expressly contemplates that FED proceedings may also include claims for past-due rent and other damages under the rental agreement. The brief never explains why that framework would not at least cover the 2004 back-rent/breach-of-lease action it discusses.

*Why it matters:* If Civ.R. 13(A) could apply to the prior rent litigation, appellant’s preclusion argument collapses and summary judgment remains sustainable.

*Anchored at:* `In their motion for summary judgment, appellees argued that appellant's claims were barred by res judicata because he failed to assert them as compulsory counte`


---

## F006 — 10 challenges pooled

**The registered vulnerability:**

> The brief quotes the adverse statutory text -- that forcible entry and detainer lies against an "occupier of lands or tenements, without color of title," which would reach this appellant whether or not she was a tenant -- and no longer answers it. The permissive "may be had" language, which is what makes the appellee's whole in-pari-materia argument work, is gone.

### `C41dc315bc5`  (framing)

The brief cannot simultaneously dismiss Reynolds and Metcalf as irrelevant and then rely on Metcalf as a cautionary illustration. More importantly, the existence of a live-in caretaker scenario in Metcalf undercuts the brief's attempt to treat all caretaker occupancy as legally simple or self-evidently nonpossessory. The brief's "distinguishable" label avoids the hard question rather than resolving it.

*Why it matters:* If the out-of-state caretaker case is at least directionally relevant, the court should be cautious about accepting the brief's categorical rule on live-in employees without a fuller statutory analysis.

*Anchored at:* `The case of Reynolds v. Clark (October 10, 2002, unpublished Cuyahoga No. 80210, 2002-Ohio-5464) cited by Appellant is not determinative of the issue present in`

### `C5b80071967`  (framing)

The brief's reliance on the word "may" in R.C. 1923.02(A) proves too much. "Proceedings under this chapter may be had as follows" identifies the statutory routes for FED; it does not authorize a landlord to bypass the chapter altogether whenever the landlord disputes tenancy. The brief never reconciles that reading with the statutory scheme limiting landlords' acts "other than as provided in Chapters 1923, 5303 and 5321" when recovering residential possession.

*Why it matters:* If R.C. 1923.02(A) is read as a list of authorized possession proceedings rather than a permission slip for self-help, the appellees' statutory defense becomes much weaker.

*Anchored at:* `Importantly, Appellant fails to include the first sentence of R.C. 1923.02(A) which precedes these two subsections on which she relies: "Proceedings under this `

### `C32f6899799`  (legal_authority)

The FED argument is built on a too-narrow premise: that only a formal residential lease can trigger Chapter 5321. But Ohio’s own definitions are broader—rental agreements can be oral, and employment-based occupancy can qualify as tenancy. So appellees’ "non-tenant" shortcut does not resolve whether Chapter 5321 applied here.

*Why it matters:* If Chapter 5321 may still govern an employee tenant or oral tenancy, then appellees did not show that they were free to bypass the residential-tenant protections appellant invokes.

*Anchored at:* `The Ohio legislature has not mandated FED procedures to be required in all situations where a "tenant holds over his term" or "the defendant is an occupier of l`

### `C7d5b7e6b89`  (legal_authority)

The brief overstates the exclusivity point. R.C. 1923.02(A) expressly includes not only tenants but also "occupier[s] of lands or tenements, without color of title," so the statute itself contemplates FED proceedings for non-tenants as well. The brief's rigid tenant-only framing ignores that statutory category and then uses the absence of tenancy to jump to a self-help result the text does not supply.

*Why it matters:* If the statute reaches occupiers, then the brief cannot defeat appellant's statutory theory simply by relabeling her as a non-tenant occupant.

*Anchored at:* `The Ohio legislature has not mandated FED procedures to be required in all situations where a "tenant holds over his term" or "the defendant is an occupier of l`

### `Cae094519da`  (missing_element)

Appellees never eliminate the essential possibility that appellant occupied the room under an employment-based tenancy. Ohio materials expressly contemplate an employee tenant, and a rental agreement may be oral or implied. The absence of a written lease or of rent paid directly to appellees does not negate that issue. At minimum, that leaves a factual question, not a basis to declare no tenancy as a matter of law.

*Why it matters:* If an employee tenancy is still legally possible on this record, the trial court could not properly grant summary judgment on the theory that tenancy was conclusively absent.

*Anchored at:* `From the foregoing, it is clear that a land owner of residential premises in a landlord-tenant relationship as defined in R.C. 5321 may not summarily lock his o`

### `Ca9460b0565`  (framing)

Appellees overread Ogle, Stone, and Amick. The supplied materials show those cases involved occupants with no rental agreement and no rent; they do not establish a universal rule that every rent-free occupant is a non-tenant. Ohio materials also recognize a separate category of employee tenancy, so a live-in caregiver cannot be automatically collapsed into the same category as a social guest or cohabitant.

*Why it matters:* If the cited cases are only fact-specific rent-free occupancy cases, then they do not control this employment-based housing dispute and cannot support affirmance as a matter of law.

*Anchored at:* `In its decision affirming the trial court's granting of summary judgment in favor of Defendant-Appellee Disbrow, the Sixth District Court of Appeals determined `

### `C4ed86604e5`  (legal_authority)

Ohio law does not make a written lease and cash rent the exclusive route to tenant status. R.C. 5321.01 defines the tenant relationship through a rental agreement, and the managed Ohio materials explain that a rental agreement may be oral or implied. They also expressly recognize an "employee tenant" when a person resides on the premises pursuant to a contract of employment. So appellees did not establish, as a matter of law, that appellant could not be a tenant merely because she lived there as part of her job and did not pay rent.

*Why it matters:* If employment-based occupancy can create tenancy, the whole premise for affirming summary judgment collapses because appellant’s tenancy-based claims cannot be defeated on a categorical no-rent/no-lease rule.

*Anchored at:* `"The court having considered all the evidence and having construed the evidence most strongly in favor of the non-moving party, determines that reasonable minds`

### `C972f3537ba`  (procedural)

Summary judgment is not justified on the record as framed by the brief because the key status question is not as one-sided as appellees claim. Their own facts show appellant was hired as a full-time caregiver, required to sleep at the home for work, and given a room as an employment accommodation. Those facts leave room for an employee-tenant or oral-arrangement theory under Ohio law, so the conclusion that she was simply a non-tenant occupant is not compelled as a matter of law.

*Why it matters:* If tenant status remained genuinely debatable, the trial court should not have entered summary judgment on the tenancy-based counts.

*Anchored at:* `Defendant-Appellee, Estate of John F. Wallace, Deceased, respectfully requests this Honorable Court overrule Appellant's sole assignment of error and affirm the`

### `C405b06fe56`  (legal_authority)

The cases the brief leans on are not fully on point for this record because the brief itself says appellant was a full-time home health care worker who had to stay overnight as part of the job. Ohio's own landlord-tenant materials recognize a distinct employee-tenant doctrine, so the rent-free residential cases the brief cites do not automatically answer whether this employment-based occupancy created possessory rights. The brief assumes the analogies instead of proving them.

*Why it matters:* If the cited cases do not control an employee-based living arrangement, then they cannot support summary judgment as a matter of law.

*Anchored at:* `In Ogle v. Disbrow, 6th Dist. Nos. L-04-1373, L-05-1102, 2005-Ohio-4869, Plaintiff-Appellant Ms. Ogle had moved into Defendant-Appellee Disbrow's house in 1999.`

### `C8d46162188`  (missing_element)

The brief treats the absence of a separate rent check and written lease as conclusive, but Ohio authority does not make those facts automatically defeat tenant status. The landlord-tenant materials recognize that a rental agreement can be oral, and they separately recognize an "employee tenant"—an employee who leases and resides in premises pursuant to a contract of employment. So the brief skips the necessary step of showing that this live-in caregiving arrangement could not, as a matter of law, amount to a tenancy or employee tenancy.

*Why it matters:* If employment-based occupancy can still be a tenancy, the core premise for rejecting the wrongful-eviction claims falls away and summary judgment cannot rest on the no-rent/no-written-lease label alone.

*Anchored at:* `Under Ohio law an individual who lives in a residence with another for whatever purpose without a rental agreement and without the payment of rent is not a tena`


---

## F007 — 10 challenges pooled

**The registered vulnerability:**

> The record the motion cites establishes posting at the premises, not certified mail. Exhibit 3, the process server's affidavit, swears she "served a Three-Day-Notice for the occupants to Leave the Premises at 8127 Cedar Road" and documents it with photographs of the notice at the property; Exhibit 12 is the notice itself, signed and dated 6-28-23. Nothing in the record is a return receipt. R.C. 1923.04(A) makes certified mail one permitted manner and personal or premises service another, and service is jurisdictional in a forcible entry and detainer action, so the brief now claims a manner of service its own record disproves on the element it can least afford to lose.

*This fixture's claim turns on the attached record. The record is in*
*`fixtures/F007/normalized/attachments/`.*

### `C29c93a22d7`  (missing_element)

The requested relief is the ultimate conclusion of the case, but the motion does not establish that the underlying possession issues are undisputed. Because the Estate’s asserted right to possession depends on the same title and notice showings attacked above, the court cannot enter partial summary judgment merely because the motion says the Estate "will" be entitled to possession. That is the issue to be proved, not assumed.

*Why it matters:* If any genuine issue remains on title, possession, or notice, the court must deny partial summary judgment and allow the FED claim to be tested at hearing or trial.

*Anchored at:* `IN THE COURT OF COMMON PLEAS GEAUGA COUNTY, OHIO
THE ESTATE OF ANTHONY NOTARIAN, MARIA SCALZO, EXECUTRIX
CASE NO. 23 M 000467
JUDGE DAVID M. ONDREY
Plaintiff,
V`

### `C9a7725597e`  (missing_element)

The motion’s reliance on the probate court’s management order is too thin. The order described in the record gives the Estate authority to inventory, collect rents, pay taxes, make repairs, and insure the property, but the brief leaps from those administrative powers to a superior right to actual possession. Sed v. Mundy, as cited by the brief, involved a will empowering sale; that is not the same thing as a general management order, so the analogy is incomplete.

*Why it matters:* If management authority is not the same as an exclusive possessory right, the Estate has not shown the statutory right to immediate possession necessary for FED relief.

*Anchored at:* `on February 1, 2023. See attached Exhibits 10 and 13. Title to property passes upon the proper execution and delivery of a deed, regardless of when or if it is `

### `C05dd981e98`  (procedural)

The notice proof is incomplete. The excerpted notice shows the warning language, but the record material supplied here does not prove the specific service method the brief asserts—certified mail, return receipt requested—nor does it supply the receipt itself. R.C. 1923.04(A) requires proof of one of the statutory notice methods, and the movant bears the burden of showing that compliance with competent evidence.

*Why it matters:* If the service method is not proven, the eviction action was not properly commenced and summary judgment on possession cannot stand.

*Anchored at:* `§1923.04(A) requires that before commencing an action for forcible entry and detain, the party seeking possession of a premises must:
notify the adverse party t`

### `C1a1d7058fc`  (remedy_scope)

A writ of restitution is premature on this record. The Estate is asking the court to convert disputed questions about title, delivery, and statutory notice into an immediate possessory remedy, but those predicate issues are not conclusively established. If there is any genuine dispute on title or R.C. 1923.04 compliance, the extraordinary remedy of restitution cannot issue on summary judgment.

*Why it matters:* Even if the court were inclined to narrow the case, it should deny the request for a writ until the necessary possession predicates are actually proven.

*Anchored at:* `IN THE COURT OF COMMON PLEAS GEAUGA COUNTY, OHIO
THE ESTATE OF ANTHONY NOTARIAN, MARIA SCALZO, EXECUTRIX
CASE NO. 23 M 000467
JUDGE DAVID M. ONDREY
Plaintiff,
V`

### `C37fdff2c06`  (factual_support)

The motion’s claim that defendants are occupiers 'without color of title' is conclusory. R.C. 1923.02(A)(5) requires that showing, but the supplied record excerpt does not independently establish its absence; it mainly recites that defendants occupy the Premises and that the Estate claims title. That is not enough under Dresher to eliminate a genuine issue on an essential element.

*Why it matters:* Without competent proof negating color of title, the Estate cannot get judgment on the FED claim as a matter of law.

*Anchored at:* `Exhibit 11. Because plaintiff is empowered to administer, manage, and sell the Premises pursuant to court orders, plaintiff has a superior right to possession.
`

### `Cb2973c3657`  (legal_authority)

The Estate’s title theory overstates what the cited materials establish. The retrieved authority says present possession may depend on present ownership of record title, but the motion never proves that the probate order and later deed conclusively vested present title in this court as a matter of law. The brief simply assumes that the deed and probate orders are enough, which is the disputed point.

*Why it matters:* Without competent proof of present title, the Estate cannot carry the possession claim based on title, and summary judgment should be denied.

*Anchored at:* `Estate. A party is subject to a forcible entry and detainer action if that party is "an occupier of lands or tenements, without color of title, and the complain`

### `C6b1a6f8492`  (framing)

The motion treats Civ.R. 56 as if a generalized affidavit-and-exhibit package automatically resolves this possession dispute, but the brief itself shows the real issues are present title, superior right to possession, and statutory notice. In a forcible-entry-and-detainer case, the court should not grant possession on a conclusory summary-judgment recitation without a clear record showing those prerequisites are undisputed.

*Why it matters:* If the court is not satisfied that the record actually eliminates the title and notice disputes, the motion fails at the threshold and possession should not be awarded summarily.

*Anchored at:* `access to the Property with a key. See attached Exhibit 3. This Motion incorporates affidavits from the property manager and undersigned counsel, exhibits 3 and`

### `C5be43f3a3b`  (missing_element)

The Estate has not established present title as a matter of law. The record shows only a probate order directing transfer, an executed deed, and a direction that the deed be filed and safekept by the court; it does not show the legally operative delivery/acceptance the brief assumes. Under the authorities the brief invokes, present possession turns on present title, and a title dispute must be resolved before eviction can be used to enforce it.

*Why it matters:* If present title is not conclusively proven, the possession claim remains fact-bound and summary judgment must be denied.

*Anchored at:* `Estate. A party is subject to a forcible entry and detainer action if that party is "an occupier of lands or tenements, without color of title, and the complain`

### `C3d36571501`  (procedural)

The motion’s reliance on affidavits and exhibits 'by reference' does not carry the Civ.R. 56 burden unless the materials themselves are competent evidence. In FED proceedings, evidentiary rules still apply, and an affidavit of facts is not automatically admissible proof. To the extent the motion depends on counsel’s affidavit or unsupported incorporated materials to establish the historical facts, that is vulnerable for lack of personal-knowledge, admissibility, and proper authentication.

*Why it matters:* If the evidentiary foundation is deficient, the court cannot find that there is no genuine issue of material fact.

*Anchored at:* `access to the Property with a key. See attached Exhibit 3. This Motion incorporates affidavits from the property manager and undersigned counsel, exhibits 3 and`

### `C91798f29b2`  (procedural)

R.C. 1923.04(A) demands strict compliance: one of the specified service methods and the statutory warning language. The motion’s description is conclusory. It says the notice was served "at the Premises" and that the warning language was included, but it does not show from the text itself which statutory method was used or otherwise eliminate the possibility of a defective notice. Ohio’s FED notice cases treat notice compliance as a mandatory prerequisite, not a loose technicality.

*Why it matters:* If notice was not strictly compliant, the court lacks a valid basis to proceed on the eviction claim and summary judgment on possession must be denied.

*Anchored at:* `§1923.04(A) requires that before commencing an action for forcible entry and detain, the party seeking possession of a premises must:
notify the adverse party t`


---

## F008 — 6 challenges pooled

**The registered vulnerability:**

> The motion is brought by a residential landlord, on facts that establish a tenancy on every page -- Friese rented the basement apartment for four years, and the res judicata argument depends on that tenancy -- and it now offers the court no answer to the theory that R.C. 5321.04 imposes a statutory landlord duty whose breach is negligence per se. What remains of its duty argument is entirely invitee premises-liability law, which does not reach a statutory duty. The defect is not that a persuasive passage went missing; it is that the motion no longer engages a duty theory its own facts invite and its own res judicata argument presupposes.

### `C0dc69a2210`  (missing_element)

Baker still has not established the critical Civ.R. 13(A) predicate: that Friese’s personal-injury claim was a compulsory counterclaim in the municipal action. The materials Baker cites do not say that every tenancy-related injury claim is compulsory, and the retrieved landlord-tenant authority shows the opposite structure in part—where an eviction complaint is only for possession, Civ.R. 13(A) does not apply, and tenant counterclaims may be permissive under Civ.R. 13(B). The record shows only that the cases involved the same tenancy; it does not show, as a matter of law, that the injury claim arose from the same transaction or occurrence as Baker’s eviction and damages claims.

*Why it matters:* Without the same-transaction/occurrence showing, Baker cannot convert omission of the claim in municipal court into a bar to this suit.

*Anchored at:* `Id. at 75, 673 N.E.2d 643, citing McCormac, Ohio Civil Rules Practice (2 Ed.1988) 199, Section 8.04.
In the case sub judice, Friese's alleged injuries occurred `

### `Cebdfef6327`  (legal_authority)

The brief overstates Ohio landlord law by saying Baker had 'no statutory duty' to install a handrail. R.C. 5321.04(A) imposes duties to comply with applicable codes and to keep the premises fit and habitable, and the retrieved authority specifically notes a basement stairway handrail duty in McHugh v. Zataar. At minimum, Baker has not shown that no applicable safety or building code required a railing here, so her categorical no-duty argument is too broad to support summary judgment.

*Why it matters:* This leaves a live duty question and defeats any attempt to win on a blanket no-handrail rule.

*Anchored at:* `under R.C. 5321.04(A) is to keep a rented premises "fit and habitable." Ohio courts have repeatedly stated that this duty of "habitability" does not encompass s`

### `C182de6eb12`  (missing_element)

Res judicata is not established unless the prior and present claims arise from the same transaction or occurrence. The record shows only that Baker later brought a municipal-court action for back rent and property damage; it does not show that Friese's separate personal-injury claim was part of that same transaction in the Civ.R. 13(A) sense. The retrieved counterclaim materials make the analysis transaction-specific and recognize that compulsory-counterclaim treatment depends on the posture and substance of the earlier case. Baker's brief never bridges the gap between a rent/property-damage collection case and a tort claim for bodily injury.

*Why it matters:* Without a clear same-transaction showing, the res judicata theory fails and summary judgment on that ground cannot stand.

*Anchored at:* `Id. at 75, 673 N.E.2d 643, citing McCormac, Ohio Civil Rules Practice (2 Ed.1988) 199, Section 8.04.
In the case sub judice, Friese's alleged injuries occurred `

### `C122ec7fcc7`  (missing_element)

Baker’s open-and-obvious theory collapses the alleged hazard into mere familiarity with the stairs. The doctrine asks whether the danger itself was open and obvious, not whether Friese knew the staircase existed. Here, the motion equates repeated use of the steps with knowledge of the specific defect Baker identifies—the missing handrail—and the record cuts the other way in part: Friese testified he did not notice anything unusual or particularly dangerous and that the steps were the same as always. On this record, Baker has not shown as a matter of law that the alleged handrail condition was so obvious that she owed no duty.

*Why it matters:* If the court accepts this, summary judgment on premises liability falls because the duty question remains for the factfinder.

*Anchored at:* `Baker does not dispute that Friese was a business invitee. But an owner of a premises is not an insurer of the safety of invitees and is obligated only to warn `

### `C465d27be04`  (legal_authority)

Armstrong's open-and-obvious rule is not enough if Friese's theory is that Baker violated landlord duties by failing to provide a required handrail. The retrieved landlord-tenant authority says R.C. 5321.04(A)(1) requires compliance with applicable building, housing, health, and safety codes, and it specifically identifies a basement stairway handrail as a recognized landlord-duty issue in McHugh v. Zataar. The same materials explain that the open-and-obvious doctrine does not apply to R.C. 5321.04 negligence-per-se claims. So Friese's awareness of the stairs does not, by itself, eliminate duty.

*Why it matters:* If a statutory or code-based handrail duty exists, the open-and-obvious defense cannot dispose of the case as a matter of law.

*Anchored at:* `Baker does not dispute that Friese was a business invitee. But an owner of a premises is not an insurer of the safety of invitees and is obligated only to warn `

### `Cf5d15710d7`  (procedural)

Even under Civ.R. 56, Baker is not entitled to judgment on this paper record because her motion depends on legal conclusions she has not established beyond genuine dispute. The record shows Friese’s familiarity with the stairs, but it also shows he said he did not notice anything unusual or particularly dangerous and did not know exactly why he fell. Those are not admissions that eliminate factual disputes on duty, obviousness, and the scope of any prior preclusion defense. Baker has therefore not carried the burden of showing there is no genuine issue of material fact and that she is entitled to judgment as a matter of law.

*Why it matters:* If the court applies the summary-judgment standard correctly, the case should proceed to trial instead of ending on a disputed written record.

*Anchored at:* `IN THE COURT OF COMMON PLEAS GEAUGA COUNTY, OHIO
JOHN FRIESE
Plaintiff
JUDGE DAVID M. ONDREY
VS.
DEFENDANT CAROLYN BAKER'S MOTION FOR SUMMARY
CAROLYN BAKER, et `

