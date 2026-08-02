"""Finished text for sub-sections the working group had not completed.

Five maintained sections stop before they give any advice. "Denied Housing"
states the client applied somewhere and was denied, then ends. "File Motion for
Relief from Judgment" says the eviction is still on the record, then closes the
letter. A catalog entry that names a topic but says nothing about it is worse
than no entry, because it looks available in the picker.

These completions are drafted, not maintained. Every one is recorded with
status `ai_drafted` so it is excluded from the default picker until an attorney
reads it, and each carries a note saying so. They deliberately stay inside what
the neighbouring maintained sections already assert about Ohio practice and add
no case citations, because a citation nobody verified is the failure mode worth
avoiding in a letter a tenant will act on.

Written to the working group's own readability rules: short sentences, plain
words, a run-in heading per paragraph. `manage.py check_readability` scores them.
"""

from __future__ import annotations

from apps.templates_app.advice_letters import STATUS_AI_DRAFTED


REVIEW_NOTE = (
    "Drafted to finish an incomplete maintained section. An attorney must read "
    "and approve it before it is sent to a client."
)


COMPLETIONS = {
    "admissions-denial-past-time": {
        "title": "Denied for Subsidized Housing - Deadline to Appeal Has Passed",
        "topic": "Misc.",
        "status": STATUS_AI_DRAFTED,
        "note": REVIEW_NOTE,
        "paragraphs": [
            "You Were Denied Housing. You applied to live at "
            "{{ fields.property_name }}. They denied you because of your record. "
            "You got the denial letter on {{ fields.denial_date }}.",
            "The Time to Ask for a Review Has Passed. Most housing programs give "
            "you a short time to ask for a review. That time has passed. So the "
            "housing provider does not have to review your denial now.",
            "You Can Still Ask. You can write to the housing provider anyway. Ask "
            "them to review your denial late. Tell them why you did not ask in "
            "time. Send the letter by mail. Keep a copy.",
            "Ask for a Change if You Have a Disability. A disability may have kept "
            "you from asking in time. If so, you can ask for a “reasonable "
            "accommodation.” That means asking them to bend a rule for you. "
            "Put your request in writing.",
            "You Can Apply Again. You can apply to other places. You can also "
            "apply again at {{ fields.property_name }} later. Ask them how long "
            "you must wait before you can re-apply.",
            "Get Your Record. Ask them for a copy of the report they used. Read it "
            "closely. If the report is wrong, write to the company that made "
            "it. Send proof of the mistake and ask them to fix it.",
            "Call Us if Something Changes. Call Legal Aid at 888-817-3777 if you "
            "get a new denial letter. Call us if they agree to review your "
            "case. Do not wait. The time to act is short.",
        ],
    },
    "file-motion-for-relief-from-judgment": {
        "title": "Asking the Court to Undo an Eviction Judgment",
        "topic": "Pro se How-To",
        "status": STATUS_AI_DRAFTED,
        "note": REVIEW_NOTE,
        "paragraphs": [
            "The Eviction Is Still on Your Record. Your landlord filed an "
            "eviction case against you. You moved out before the court-ordered "
            "move-out date. Even so, the court still ruled against you. That "
            "ruling stays on your record.",
            "You Can Ask the Court to Undo the Ruling. You can ask the court to "
            "undo what it decided. You do this with a form called a Motion for "
            "Relief from Judgment. You can do this without a lawyer.",
            "You Need a Good Reason. The court will not undo a ruling just "
            "because you disagree with it. You must give the court a reason the "
            "law allows. Common reasons are:",
            "- You never got the court papers, so you did not know about the "
            "hearing.",
            "- Something outside your control kept you from going to the hearing.",
            "- You have new proof you could not have found before the hearing.",
            "- The landlord misled the court.",
            "Explain Your Defense. You must also tell the court what you would "
            "have said at the hearing. Explain why the court would have ruled "
            "differently if you had been there.",
            "Ask Quickly. Ask the court as soon as you can. The court can say no "
            "just because you waited. Some reasons must be raised within one "
            "year of the ruling.",
            "How to Turn It In. Take your form to the Clerk of Courts. Bring extra "
            "copies. Mail one copy to your landlord. If your landlord has a "
            "lawyer, mail it to the lawyer instead. The court's Housing "
            "Specialists can help you. Call them at 216-664-4295.",
            "You May Want to Seal the Record Instead. Undoing a ruling is hard. It "
            "is often easier to ask the court to hide the case from its "
            "website. This is called sealing the record. Ask the Housing "
            "Specialists about both choices first.",
        ],
    },
    "holdover-tenant": {
        "title": "Moving with a Housing Choice Voucher",
        "topic": "HCV",
        "status": STATUS_AI_DRAFTED,
        "note": (
            "The maintained file named \"Holdover tenant\" in fact contains "
            "advice about moving with a voucher, so it is catalogued under its "
            "real subject. The catalog's separate \"Holdover\" row has no "
            "maintained text yet. " + REVIEW_NOTE
        ),
        "paragraphs": [
            "You Have a Housing Choice Voucher. You told us you have a Housing "
            "Choice Voucher. You can use your voucher to move to a new home.",
            "Start Now. Call the Housing Authority as soon as you can. Ask them "
            "what you must do to move. Most housing authorities make you go to a "
            "class first. Then they give you a paper that lets you look for a new "
            "home.",
            "Moving Takes Time. The Housing Authority must check any new home "
            "before you can move in. This check can take months. Start looking "
            "early so you do not run out of time.",
            "You Will Probably Keep Your Voucher. A landlord who does not renew a "
            "lease rarely costs a tenant their voucher. So this case by itself "
            "should not cost you yours.",
            "Call Us if You Get a Notice. The Housing Authority may send you a "
            "letter saying it plans to end your voucher. If it does, call Legal "
            "Aid right away at 888-817-3777. You have only a short time to ask "
            "for a hearing.",
        ],
    },
    "vawa": {
        "title": "VAWA Notices in Subsidized Housing",
        "topic": "Presenting Defenses",
        "status": STATUS_AI_DRAFTED,
        "note": REVIEW_NOTE,
        "paragraphs": [
            "Your Landlord Owes You Extra Notices. Your housing is subsidized. "
            "Because of that, your landlord must give you two extra notices "
            "before evicting you. These come from a federal law called VAWA, the "
            "Violence Against Women Act.",
            "The Law Covers Everyone. Your landlord owes you these notices even if "
            "no violence happened in your home. The law is not only for women. "
            "It is not only for people who were hurt.",
            "You Did Not Get Them. You told us your landlord did not give you "
            "these notices. If that is right, the court should close, or "
            "“dismiss,” the case.",
            "What to Say in Court. When the judge says it is your turn, say:",
            "- “Your Honor, my housing is subsidized.”",
            "- “My landlord never gave me the VAWA notices.”",
            "- “Please dismiss this eviction.”",
            "Bring Your Papers. Bring anything showing your housing is "
            "subsidized. A copy of your lease or a letter from the Housing "
            "Authority works well.",
            "What Happens Next. The judge may close the case. Your landlord can "
            "then give you the notices and start over. Call our Intake team at "
            "888-817-3777 if you get new court papers.",
        ],
    },
    "negotiate-move-out-neo": {
        "title": "Settling Your Case Without a Judgment",
        "topic": "Nonpayment",
        "status": STATUS_AI_DRAFTED,
        "note": (
            "Expanded from a 105-word maintained section that listed two options "
            "without explaining them. " + REVIEW_NOTE
        ),
        "paragraphs": [
            "Go to Your Hearing. You must go to your eviction hearing. If you do "
            "not go, the judge will probably rule against you.",
            "Why Settling Helps. A ruling against you stays on your record. "
            "Landlords look for it when you apply for a new home. If you and your "
            "landlord agree on a plan, you may avoid that ruling.",
            "Move Before Court. You can move out and give the keys back before "
            "the hearing. Take a picture of the keys, or ask for a receipt. Tell "
            "the judge at the hearing that you moved and gave back the keys. Then "
            "ask the judge to dismiss the case.",
            "Agree to a Move-out Date in Court. Have you not moved yet? Ask the "
            "judge to help you and your landlord pick a move-out date. Ask for "
            "as much time as you need. Court staff can help you write it down.",
            "Check the Paper Before You Sign. The paper must say the case is "
            "closed if you move by the agreed date. Look for that sentence. "
            "Without it, the eviction can stay on your record even if you keep "
            "your promise.",
            "Get a Copy. Ask for a copy of anything you sign before you leave the "
            "courthouse. Keep it somewhere safe.",
        ],
    },
}
