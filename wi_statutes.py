import json
import re
from typing import List, Dict, Optional


WI_CRIMINAL_STATUTES = [
    {"code": "940.01", "title": "First-Degree Intentional Homicide", "category": "Homicide", "description": "Whoever causes the death of another human being with intent to kill that person or another"},
    {"code": "940.02", "title": "First-Degree Reckless Homicide", "category": "Homicide", "description": "Causes the death of another human being by recklessly engaging in conduct which creates an unreasonable and substantial risk of death"},
    {"code": "940.05", "title": "Second-Degree Intentional Homicide", "category": "Homicide", "description": "Whoever causes the death of another human being with intent to kill that person or another"},
    {"code": "940.06", "title": "Second-Degree Reckless Homicide", "category": "Homicide", "description": "Whoever causes the death of another human being by criminally reckless conduct"},
    {"code": "940.09(1)(a)", "title": "Homicide by Intoxicated Use of Vehicle or Firearm", "category": "Homicide", "description": "Causes the death of another by operation of a vehicle or use of a firearm while under the influence"},
    {"code": "940.03", "title": "Felony Murder", "category": "Homicide", "description": "Whoever causes the death of another human being while committing or attempting to commit a felony"},
    {"code": "940.07", "title": "Homicide by Negligent Control of Vicious Animal", "category": "Homicide", "description": "Causes the death of another by negligently allowing a vicious animal to run at large"},
    {"code": "940.08", "title": "Homicide by Negligent Handling of Dangerous Weapon", "category": "Homicide", "description": "Causes the death of another by negligent handling or operation of a dangerous weapon, explosives, or fire"},
    {"code": "940.10", "title": "Homicide by Negligent Operation of Vehicle", "category": "Homicide", "description": "Causes the death of another by the negligent operation of a vehicle"},
    {"code": "940.11", "title": "Mutilating or Hiding a Corpse", "category": "Homicide", "description": "Whoever mutilates, dismembers, or conceals a corpse with intent to conceal a crime"},
    {"code": "940.12", "title": "Assisting Suicide", "category": "Homicide", "description": "Whoever with intent that another take his or her own life assists such person to commit suicide"},
    {"code": "940.60(1)", "title": "Battery", "category": "Assault", "description": "Whoever causes bodily harm to another by an act done with intent to cause bodily harm to that person or another without consent (Class A misdemeanor)"},
    {"code": "940.60(2)", "title": "Substantial Battery", "category": "Assault", "description": "Whoever causes substantial bodily harm to another by an act done with intent to cause bodily harm (Class I felony)"},
    {"code": "940.60(3)(a)", "title": "Aggravated Battery — Great Bodily Harm", "category": "Assault", "description": "Whoever causes great bodily harm to another by an act done with intent to cause bodily harm (Class H felony)"},
    {"code": "940.62(1)(a)", "title": "Battery to Public Officers", "category": "Assault", "description": "Battery to a public officer in order to influence official action or as a result of official action (Class I felony)"},
    {"code": "940.62(2)(a)", "title": "Battery to Judges, Prosecutors, Law Enforcement, Witnesses", "category": "Assault", "description": "Battery to judge, prosecutor, law enforcement officer, witness, or their family members in response to official actions (Class H felony)"},
    {"code": "940.225(1)", "title": "First-Degree Sexual Assault", "category": "Sexual Assault", "description": "Sexual contact or intercourse by use or threat of force or violence"},
    {"code": "940.225(2)", "title": "Second-Degree Sexual Assault", "category": "Sexual Assault", "description": "Sexual contact or intercourse with person who is physically helpless or by use of a weapon"},
    {"code": "940.225(3)", "title": "Third-Degree Sexual Assault", "category": "Sexual Assault", "description": "Sexual intercourse without consent"},
    {"code": "940.225(4)", "title": "Fourth-Degree Sexual Assault", "category": "Sexual Assault", "description": "Sexual contact without consent"},
    {"code": "940.30", "title": "False Imprisonment", "category": "Kidnapping", "description": "Whoever intentionally confines or restrains another without consent"},
    {"code": "940.31(1)", "title": "Kidnapping", "category": "Kidnapping", "description": "Takes a person from one place to another by force or threat of force"},
    {"code": "940.21", "title": "Mayhem", "category": "Assault", "description": "Whoever injures another by permanently disfiguring, disabling, or amputating a body part"},
    {"code": "940.23", "title": "Reckless Injury", "category": "Assault", "description": "Whoever recklessly causes great bodily harm to another"},
    {"code": "940.235", "title": "Strangulation and Suffocation", "category": "Assault", "description": "Whoever strangles or suffocates another"},
    {"code": "940.24", "title": "Injury by Negligent Handling of Dangerous Weapon", "category": "Assault", "description": "Causes bodily harm to another by negligent handling of a dangerous weapon, explosives, or fire"},
    {"code": "940.25", "title": "Injury by Intoxicated Use of Vehicle", "category": "Assault", "description": "Causes great bodily harm to another by operation of a vehicle while under the influence"},
    {"code": "940.285", "title": "Abuse of Individuals at Risk", "category": "Assault", "description": "Whoever intentionally causes bodily harm to an individual at risk"},
    {"code": "940.302", "title": "Human Trafficking", "category": "Assault", "description": "Whoever knowingly recruits, transports, or obtains a person for forced labor or commercial sex acts"},
    {"code": "940.305", "title": "Taking Hostages", "category": "Kidnapping", "description": "Whoever takes or holds another as a hostage"},
    {"code": "940.315", "title": "Unauthorized Use of GPS Tracking Device", "category": "Public Order", "description": "Intentionally places a GPS tracking device on another's vehicle without consent"},
    {"code": "940.32", "title": "Stalking", "category": "Public Order", "description": "Whoever intentionally engages in a course of conduct that causes serious emotional distress or fear"},
    {"code": "940.42", "title": "Intimidation of Witnesses (Misdemeanor)", "category": "Public Order", "description": "Threatens or intimidates a witness with intent to influence testimony"},
    {"code": "940.43", "title": "Intimidation of Witnesses (Felony)", "category": "Public Order", "description": "Intimidates a witness by force or threat of force"},
    {"code": "940.48", "title": "Violation of Court Orders", "category": "Public Order", "description": "Knowingly violates a court order issued under domestic abuse or harassment statutes"},
    {"code": "940.65", "title": "Battery to an Unborn Child", "category": "Assault", "description": "Whoever causes bodily harm to an unborn child"},
    {"code": "940.66", "title": "Battery to an Elder Person or Adult at Risk", "category": "Assault", "description": "Whoever causes bodily harm to an elder person or adult at risk"},
    {"code": "940.34", "title": "Duty to Aid Victim or Report Crime", "category": "Public Order", "description": "Knowingly fails to give aid or notify law enforcement after witnessing a crime involving bodily harm"},
    {"code": "940.291", "title": "Law Enforcement Officer; Failure to Render Aid", "category": "Public Order", "description": "A law enforcement officer who fails to render or summon aid to an injured person"},
    {"code": "940.44", "title": "Intimidation of Victims (Misdemeanor)", "category": "Public Order", "description": "Threatens or intimidates a victim with intent to influence cooperation"},
    {"code": "940.45", "title": "Intimidation of Victims (Felony)", "category": "Public Order", "description": "Intimidates a victim by force or threat of force"},
    {"code": "940.49", "title": "Violation of Pretrial Release Conditions", "category": "Public Order", "description": "Violates conditions of pretrial release"},
    {"code": "941.20(1)", "title": "Endangering Safety by Use of Dangerous Weapon", "category": "Weapons", "description": "Endangers safety of another by negligent handling of a dangerous weapon"},
    {"code": "941.23", "title": "Carrying a Concealed Weapon", "category": "Weapons", "description": "Carries a concealed weapon on the person"},
    {"code": "941.26(2)", "title": "Machine Guns and Other Automatic Firearms", "category": "Weapons", "description": "Possesses a machine gun or other fully automatic weapon"},
    {"code": "941.28", "title": "Possession of Short-Barreled Shotgun or Short-Barreled Rifle", "category": "Weapons", "description": "Possesses a short-barreled shotgun or short-barreled rifle"},
    {"code": "941.29", "title": "Possession of a Firearm", "category": "Weapons", "description": "Possesses a firearm after having been convicted of a felony"},
    {"code": "941.30", "title": "Recklessly Endangering Safety", "category": "Weapons", "description": "Recklessly endangers another's safety by conduct regardless of life"},
    {"code": "941.21", "title": "Disarming an Officer", "category": "Weapons", "description": "Intentionally disarms a peace officer or correctional officer of a dangerous weapon"},
    {"code": "941.231", "title": "Carrying a Concealed Knife", "category": "Weapons", "description": "Carries a concealed knife on the person"},
    {"code": "941.235", "title": "Carrying Firearm in Public Building", "category": "Weapons", "description": "Carries a firearm into a public building"},
    {"code": "941.237", "title": "Carrying Handgun Where Alcohol Sold", "category": "Weapons", "description": "Carries a handgun into a premises where alcohol beverages may be sold and consumed"},
    {"code": "941.2905", "title": "Straw Purchasing of Firearms", "category": "Weapons", "description": "Knowingly purchases a firearm on behalf of a person prohibited from possessing a firearm"},
    {"code": "941.291", "title": "Possession of Body Armor by Felon", "category": "Weapons", "description": "Possesses body armor after having been convicted of a felony"},
    {"code": "941.292", "title": "Possession of a Weaponized Drone", "category": "Weapons", "description": "Possesses a drone equipped with a dangerous weapon"},
    {"code": "941.295", "title": "Possession of Electric Weapon", "category": "Weapons", "description": "Possesses an electric weapon, such as a stun gun or taser"},
    {"code": "941.296", "title": "Use of Handgun and Armor-Piercing Bullet During Crime", "category": "Weapons", "description": "Possesses a handgun and armor-piercing bullet while committing a crime"},
    {"code": "941.298", "title": "Firearm Silencers", "category": "Weapons", "description": "Manufactures, sells, or possesses a firearm silencer"},
    {"code": "941.31", "title": "Possession of Explosives", "category": "Weapons", "description": "Intentionally possesses explosives without lawful purpose"},
    {"code": "941.375", "title": "Throwing or Discharging Bodily Fluids at Public Safety Worker", "category": "Public Order", "description": "Throws or discharges bodily fluids at a public safety worker"},
    {"code": "941.38", "title": "Criminal Gang Member Solicitation", "category": "Public Order", "description": "Solicits or recruits another to join a criminal gang"},
    {"code": "941.39", "title": "Victim, Witness, Juror, or Co-Actor Contact", "category": "Public Order", "description": "Contacts a victim, witness, juror, or co-actor in violation of a court order"},
    {"code": "941.13", "title": "False Alarms", "category": "Public Order", "description": "Intentionally gives a false alarm to any public officer or employee"},
    {"code": "941.35", "title": "Emergency Telephone Calls (911 Abuse)", "category": "Public Order", "description": "Makes a telephone call to 911 or an emergency number with intent to harass or without a legitimate emergency"},
    {"code": "941.37", "title": "Obstructing Emergency or Rescue Personnel", "category": "Public Order", "description": "Intentionally obstructs, interferes with, or hinders emergency or rescue personnel"},
    {"code": "942.01", "title": "Defamation", "category": "Public Order", "description": "Communicates defamatory matter to a third person with intent to defame"},
    {"code": "942.05", "title": "Opening Letters", "category": "Public Order", "description": "Intentionally opens any sealed letter or package addressed to another without consent"},
    {"code": "942.08", "title": "Invasion of Privacy", "category": "Public Order", "description": "Intentionally views, photographs, or records a nude or partially nude person without consent in a private place"},
    {"code": "942.09", "title": "Representations Depicting Nudity (Revenge Porn)", "category": "Public Order", "description": "Intentionally posts or distributes a representation depicting nudity without consent with intent to cause harm"},
    {"code": "942.095", "title": "Sexual Extortion", "category": "Public Order", "description": "Threatens to disclose intimate representations to coerce another into sexual acts"},
    {"code": "942.10", "title": "Use of a Drone", "category": "Public Order", "description": "Operates a drone to intentionally photograph or record a person in a private place without consent"},
    {"code": "943.10(1)", "title": "Burglary", "category": "Burglary", "description": "Intentionally enters a building or dwelling without consent with intent to steal"},
    {"code": "943.10(2)", "title": "Burglary of a Building or Dwelling", "category": "Burglary", "description": "Intentionally enters a building or dwelling without consent"},
    {"code": "943.13", "title": "Trespass to Land", "category": "Burglary", "description": "Enters land of another after having been notified not to enter"},
    {"code": "943.14", "title": "Criminal Trespass to Dwellings", "category": "Burglary", "description": "Intentionally enters the dwelling of another without consent"},
    {"code": "943.20(1)", "title": "Theft", "category": "Theft", "description": "Intentionally takes and carries away movable property of another without consent"},
    {"code": "943.20(3)(a)", "title": "Theft — Value $2,500 or Less", "category": "Theft", "description": "Class A misdemeanor theft of property valued at $2,500 or less"},
    {"code": "943.20(3)(bf)", "title": "Theft — Value $2,500 to $5,000", "category": "Theft", "description": "Class I felony theft of property valued between $2,500 and $5,000"},
    {"code": "943.20(3)(bm)", "title": "Theft — Value $5,000 to $10,000", "category": "Theft", "description": "Class H felony theft of property valued between $5,000 and $10,000"},
    {"code": "943.20(3)(c)", "title": "Theft — Value $10,000 to $100,000", "category": "Theft", "description": "Class G felony theft of property valued over $10,000 but not exceeding $100,000"},
    {"code": "943.20(3)(cm)", "title": "Theft — Value Over $100,000", "category": "Theft", "description": "Class F felony theft of property valued over $100,000"},
    {"code": "943.23(1g)", "title": "Operating Vehicle Without Owner's Consent", "category": "Theft", "description": "Intentionally operates a vehicle without the owner's consent"},
    {"code": "943.23(3)", "title": "Operating Vehicle Without Consent — Passenger", "category": "Theft", "description": "Knowingly rides in a vehicle taken without owner's consent"},
    {"code": "943.32(1)", "title": "Robbery", "category": "Robbery", "description": "By use of force or threat of force takes property from another"},
    {"code": "943.32(2)", "title": "Armed Robbery", "category": "Robbery", "description": "Robbery while armed with a dangerous weapon"},
    {"code": "943.34(1)", "title": "Receiving Stolen Property", "category": "Theft", "description": "Intentionally receives or conceals stolen property knowing it was stolen"},
    {"code": "943.38(1)", "title": "Forgery", "category": "Fraud", "description": "Makes or alters a writing to defraud"},
    {"code": "943.201", "title": "Identity Theft", "category": "Fraud", "description": "Intentionally uses or attempts to use personal identifying information or documents of another without consent"},
    {"code": "943.41(1)", "title": "Financial Transaction Card Crimes", "category": "Fraud", "description": "Fraudulent use of a financial transaction card"},
    {"code": "943.01", "title": "Criminal Damage to Property", "category": "Crimes Against Property", "description": "Intentionally causes damage to another's property"},
    {"code": "943.02", "title": "Arson of Buildings", "category": "Crimes Against Property", "description": "Intentionally sets fire to or burns a building"},
    {"code": "943.03", "title": "Arson of Property Other Than Building", "category": "Crimes Against Property", "description": "Intentionally sets fire to or burns property other than a building"},
    {"code": "943.04", "title": "Arson With Intent to Defraud", "category": "Crimes Against Property", "description": "Intentionally burns property with intent to defraud an insurer"},
    {"code": "943.11", "title": "Entry Into Locked Vehicle", "category": "Burglary", "description": "Intentionally enters a locked vehicle without consent"},
    {"code": "943.12", "title": "Possession of Burglarious Tools", "category": "Burglary", "description": "Possesses burglarious tools with intent to commit a crime"},
    {"code": "943.145", "title": "Criminal Trespass to a Medical Facility", "category": "Public Order", "description": "Intentionally enters a medical facility without consent under circumstances tending to provoke a breach of peace"},
    {"code": "943.204", "title": "Theft of Mail", "category": "Theft", "description": "Intentionally takes mail from a mail receptacle without consent"},
    {"code": "943.21", "title": "Fraud on Hotel, Restaurant, or Gas Station", "category": "Fraud", "description": "Obtains food, lodging, or services with intent to defraud"},
    {"code": "943.231", "title": "Carjacking", "category": "Robbery", "description": "By use of force or threat of force takes a motor vehicle from another"},
    {"code": "943.24", "title": "Issue of Worthless Check", "category": "Fraud", "description": "Issues a check drawn on insufficient funds with intent to defraud"},
    {"code": "943.30", "title": "Threats to Injure or Accuse of Crime", "category": "Public Order", "description": "Threatens to injure or accuse another of a crime with intent to extort money or property"},
    {"code": "943.31", "title": "Threats to Communicate Derogatory Information", "category": "Public Order", "description": "Threatens to communicate derogatory information with intent to extort"},
    {"code": "943.37", "title": "Alteration of Property Identification Marks", "category": "Crimes Against Property", "description": "Removes, alters, or obliterates identification marks on property"},
    {"code": "944.06", "title": "Incest", "category": "Sex Offenses", "description": "Marries or has sexual intercourse with a close blood relative"},
    {"code": "944.16", "title": "Adultery", "category": "Sex Offenses", "description": "Married person who has sexual intercourse with another not their spouse"},
    {"code": "944.21(1)", "title": "Obscene Material or Performance", "category": "Sex Offenses", "description": "Sells, distributes, or exhibits obscene material"},
    {"code": "944.30", "title": "Prostitution", "category": "Sex Offenses", "description": "Whoever engages in sexual intercourse or acts for a fee"},
    {"code": "944.05", "title": "Bigamy", "category": "Sex Offenses", "description": "Contracts a marriage with knowledge that a prior marriage is not dissolved"},
    {"code": "944.15", "title": "Public Fornication", "category": "Sex Offenses", "description": "Has sexual intercourse in a public place"},
    {"code": "944.17", "title": "Sexual Gratification", "category": "Sex Offenses", "description": "Performs a sex act for the purpose of sexual gratification"},
    {"code": "944.18", "title": "Bestiality", "category": "Sex Offenses", "description": "Whoever sexually penetrates or contacts an animal"},
    {"code": "944.20", "title": "Lewd and Lascivious Behavior", "category": "Sex Offenses", "description": "Commits a lewd or indecent act in public"},
    {"code": "944.21(2)", "title": "Possession of Obscene Material", "category": "Sex Offenses", "description": "Knowingly possesses obscene material"},
    {"code": "944.25", "title": "Sending Obscene or Sexually Explicit Electronic Messages", "category": "Sex Offenses", "description": "Sends obscene or sexually explicit messages via electronic communication"},
    {"code": "944.31", "title": "Patronizing Prostitutes", "category": "Sex Offenses", "description": "Whoever hires or offers to hire a person to engage in sexual acts for a fee"},
    {"code": "944.32", "title": "Soliciting Prostitutes", "category": "Sex Offenses", "description": "Solicits another to engage in prostitution"},
    {"code": "944.33", "title": "Pandering", "category": "Sex Offenses", "description": "Compels another to become a prostitute"},
    {"code": "944.34", "title": "Keeping a Place of Prostitution", "category": "Sex Offenses", "description": "Keeps or maintains a place of prostitution"},
    {"code": "945.02", "title": "Gambling", "category": "Gambling", "description": "Whoever makes a bet or conducts gambling activities"},
    {"code": "945.03", "title": "Commercial Gambling", "category": "Gambling", "description": "Whoever conducts organized gambling for profit"},
    {"code": "945.04", "title": "Permitting Premises for Commercial Gambling", "category": "Gambling", "description": "Knowingly permits premises to be used for commercial gambling"},
    {"code": "946.41", "title": "Resisting or Obstructing an Officer", "category": "Public Order", "description": "Intentionally resists or obstructs a law enforcement officer"},
    {"code": "946.415", "title": "Failure to Comply With Officer's Attempt to Take Person Into Custody", "category": "Public Order", "description": "Intentionally fails to stop when ordered by a law enforcement officer attempting to take the person into custody"},
    {"code": "946.42", "title": "Escape", "category": "Public Order", "description": "Intentionally escapes from lawful custody"},
    {"code": "946.46", "title": "Encouraging Violation of Probation, Extended Supervision or Parole", "category": "Public Order", "description": "Intentionally encourages or helps a person violate conditions of probation, extended supervision, or parole"},
    {"code": "946.47", "title": "Harboring or Aiding Felons", "category": "Public Order", "description": "Harbors or conceals a person knowing that person has committed a felony"},
    {"code": "946.48", "title": "Kidnapped or Missing Persons; False Information", "category": "Public Order", "description": "Provides false information regarding a kidnapped or missing person"},
    {"code": "946.49(1)", "title": "Felony Bail Jumping", "category": "Public Order", "description": "Failure to comply with bail conditions while charged with a felony"},
    {"code": "946.49(2)", "title": "Misdemeanor Bail Jumping", "category": "Public Order", "description": "Failure to comply with bail conditions while charged with a misdemeanor"},
    {"code": "946.50", "title": "Absconding", "category": "Public Order", "description": "Intentionally absconds after being charged with a crime or violating probation"},
    {"code": "946.10", "title": "Bribery of Public Officers and Employees", "category": "Public Order", "description": "Offers a bribe to a public officer to influence official action"},
    {"code": "946.12", "title": "Misconduct in Public Office", "category": "Public Order", "description": "Public officer who does an act in excess of lawful authority with intent to gain benefit or harm"},
    {"code": "946.31", "title": "Perjury", "category": "Public Order", "description": "Knowingly makes a false statement under oath"},
    {"code": "946.32", "title": "False Swearing", "category": "Public Order", "description": "Knowingly makes a false statement under oath not in a judicial proceeding"},
    {"code": "946.40", "title": "Refusing to Aid Officer", "category": "Public Order", "description": "Refuses to assist a law enforcement officer upon command"},
    {"code": "946.43", "title": "Assaults by Prisoners", "category": "Public Order", "description": "A prisoner who intentionally causes bodily harm to another"},
    {"code": "946.44", "title": "Assisting or Permitting Escape", "category": "Public Order", "description": "Intentionally assists or permits a prisoner to escape"},
    {"code": "946.61", "title": "Bribery of Witnesses", "category": "Public Order", "description": "Offers a bribe to a witness to influence testimony"},
    {"code": "946.64", "title": "Communicating With Jurors", "category": "Public Order", "description": "Improperly communicates with a juror about a case"},
    {"code": "946.65", "title": "Obstructing Justice", "category": "Public Order", "description": "Intentionally obstructs, delays, or prevents the administration of justice"},
    {"code": "946.69", "title": "Impersonating a Public Officer", "category": "Public Order", "description": "Falsely assumes or pretends to be a public officer"},
    {"code": "946.70", "title": "Impersonating Peace Officers or Emergency Personnel", "category": "Public Order", "description": "Falsely represents oneself as a peace officer, fire fighter, or emergency personnel"},
    {"code": "946.72", "title": "Tampering With Public Records and Notices", "category": "Public Order", "description": "Intentionally destroys, mutilates, or conceals a public record"},
    {"code": "946.52", "title": "Failure to Submit to Biological Specimen (DNA)", "category": "Public Order", "description": "Fails to provide a biological specimen after being convicted of a felony or certain misdemeanors"},
    {"code": "947.01", "title": "Disorderly Conduct", "category": "Public Order", "description": "Engages in violent, abusive, or disorderly conduct under circumstances that cause a disturbance"},
    {"code": "947.012", "title": "Unlawful Use of Telephone", "category": "Public Order", "description": "Makes telephone calls with intent to frighten, intimidate, threaten, abuse, or harass"},
    {"code": "947.0125", "title": "Unlawful Use of Computerized Communication Systems", "category": "Public Order", "description": "Uses a computerized communication system with intent to frighten, intimidate, threaten, abuse, or harass"},
    {"code": "947.013", "title": "Harassment", "category": "Public Order", "description": "Strikes, shoves, kicks or otherwise subjects another to physical contact"},
    {"code": "947.011", "title": "Disrupting a Funeral or Memorial Service", "category": "Public Order", "description": "Engages in disorderly conduct at a funeral or memorial service with intent to disrupt"},
    {"code": "947.014", "title": "Swatting", "category": "Public Order", "description": "Knowingly makes a false report of an emergency to cause a law enforcement response"},
    {"code": "947.015", "title": "Bomb Scares", "category": "Public Order", "description": "Knowingly makes a false report of a bomb or explosive"},
    {"code": "947.016", "title": "Threatening to Cause Bodily Harm", "category": "Public Order", "description": "Threatens to cause bodily harm to another"},
    {"code": "947.019", "title": "Terrorist Threats", "category": "Public Order", "description": "Threatens to commit an act of terrorism"},
    {"code": "947.06", "title": "Unlawful Assemblies", "category": "Public Order", "description": "Participates in an unlawful assembly likely to cause injury or breach of peace"},
    {"code": "948.02(1)", "title": "First-Degree Sexual Assault of a Child", "category": "Child Protection", "description": "Sexual contact or intercourse with a child under age 12"},
    {"code": "948.02(2)", "title": "Second-Degree Sexual Assault of a Child", "category": "Child Protection", "description": "Sexual contact or intercourse with a child under age 16"},
    {"code": "948.025(1)", "title": "Repeated Sexual Assault of Same Child", "category": "Child Protection", "description": "Two or more violations of sexual assault of a child"},
    {"code": "948.03(2)", "title": "Physical Abuse of a Child", "category": "Child Protection", "description": "Intentionally causes bodily harm to a child"},
    {"code": "948.07", "title": "Child Enticement", "category": "Child Protection", "description": "Entices a child into a vehicle, building or secluded place"},
    {"code": "948.09", "title": "Sexual Intercourse with a Child Age 16 or Older", "category": "Child Protection", "description": "Sexual intercourse with a child 16 or older by a person who works with children"},
    {"code": "948.10", "title": "Exposing Genitals to a Child", "category": "Child Protection", "description": "Intentionally exposes genitals to a child"},
    {"code": "948.11(1)", "title": "Exposing a Child to Harmful Material", "category": "Child Protection", "description": "Knowingly sells, distributes, or exhibits harmful material to a child"},
    {"code": "948.40", "title": "Contributing to the Delinquency of a Child", "category": "Child Protection", "description": "Knowingly encourages or contributes to a child's delinquency"},
    {"code": "948.55(1)", "title": "Leaving or Storing a Loaded Firearm Within Reach of a Child", "category": "Child Protection", "description": "Recklessly stores or leaves a loaded firearm within reach or easy access of a child"},
    {"code": "948.60", "title": "Possession of a Dangerous Weapon by a Person Under 18", "category": "Weapons", "description": "Child under 18 possesses a dangerous weapon"},
    {"code": "948.04", "title": "Causing Mental Harm to a Child", "category": "Child Protection", "description": "Intentionally causes mental harm to a child"},
    {"code": "948.05", "title": "Sexual Exploitation of a Child", "category": "Child Protection", "description": "Permits or causes a child to engage in sexually explicit conduct for a performance"},
    {"code": "948.051", "title": "Trafficking of a Child", "category": "Child Protection", "description": "Knowingly recruits, transports, or obtains a child for forced labor or commercial sex acts"},
    {"code": "948.06", "title": "Incest With a Child", "category": "Child Protection", "description": "Marries or has sexual intercourse with a child who is a close blood relative"},
    {"code": "948.072", "title": "Grooming of a Child for Sexual Activity", "category": "Child Protection", "description": "Engages in a course of conduct to prepare a child for sexual activity"},
    {"code": "948.075", "title": "Use of Computer to Facilitate a Child Sex Crime", "category": "Child Protection", "description": "Uses a computer to facilitate a sex crime against a child"},
    {"code": "948.08", "title": "Soliciting a Child for Prostitution", "category": "Child Protection", "description": "Solicits or arranges to meet a child for prostitution"},
    {"code": "948.12", "title": "Possession of Child Pornography", "category": "Child Protection", "description": "Knowingly possesses child pornography"},
    {"code": "948.13", "title": "Child Sex Offender Working With Children", "category": "Child Protection", "description": "A registered child sex offender who works with children"},
    {"code": "948.20", "title": "Abandonment of a Child", "category": "Child Protection", "description": "Intentionally abandons a child under age 18"},
    {"code": "948.21", "title": "Neglecting a Child", "category": "Child Protection", "description": "Intentionally fails to provide necessary care, food, or shelter for a child"},
    {"code": "948.30", "title": "Abduction of Another's Child", "category": "Child Protection", "description": "Intentionally takes another's child with intent to keep or conceal the child"},
    {"code": "948.31", "title": "Interference With Custody by Parent", "category": "Child Protection", "description": "Intentionally takes a child from the lawful custodian"},
    {"code": "948.51", "title": "Hazing", "category": "Child Protection", "description": "Engages in acts that endanger the health or safety of a student for initiation purposes"},
    {"code": "948.605", "title": "Gun-Free School Zones", "category": "Weapons", "description": "Knowingly possesses a firearm in a school zone"},
    {"code": "948.61", "title": "Dangerous Weapons on School Premises", "category": "Weapons", "description": "Carries a dangerous weapon on school premises"},
    {"code": "951.02", "title": "Mistreating Animals", "category": "Crimes Against Property", "description": "Treats any animal in a cruel manner causing unnecessary and excessive pain"},
    {"code": "951.03", "title": "Dognapping and Catnapping", "category": "Crimes Against Property", "description": "Takes the dog or cat of another without consent"},
    {"code": "951.06", "title": "Use of Poisonous Substances on Animals", "category": "Crimes Against Property", "description": "Intentionally administers poison or a controlled substance to an animal"},
    {"code": "951.08", "title": "Instigating Fights Between Animals (Dogfighting)", "category": "Crimes Against Property", "description": "Causes or permits animals to fight for amusement or gain"},
    {"code": "951.095", "title": "Harassment of Police, Fire, and Search and Rescue Dogs", "category": "Public Order", "description": "Intentionally harms or interferes with a police, fire, or search and rescue dog"},
    {"code": "951.097", "title": "Harassment of Service Dogs", "category": "Public Order", "description": "Intentionally harms or interferes with a service dog"},
    {"code": "951.13", "title": "Providing Proper Food and Drink to Confined Animals", "category": "Crimes Against Property", "description": "Fails to provide adequate food and drink to a confined animal"},
    {"code": "951.14", "title": "Providing Proper Shelter to Confined Animals", "category": "Crimes Against Property", "description": "Fails to provide proper shelter to a confined animal"},
    {"code": "951.15", "title": "Abandoning Animals", "category": "Crimes Against Property", "description": "Abandons any animal without providing for its care"},
    {"code": "961.41(1)(a)", "title": "Manufacture/Deliver Heroin", "category": "Drugs", "description": "Manufactures or delivers heroin"},
    {"code": "961.41(1)(cm)", "title": "Manufacture/Deliver Cocaine", "category": "Drugs", "description": "Manufactures or delivers cocaine"},
    {"code": "961.41(1)(h)", "title": "Manufacture/Deliver Marijuana", "category": "Drugs", "description": "Manufactures or delivers marijuana"},
    {"code": "961.41(2)(g)", "title": "Possession of Marijuana", "category": "Drugs", "description": "Possession of marijuana or hashish"},
    {"code": "961.41(3g)(c)", "title": "Possession of Cocaine", "category": "Drugs", "description": "Possession of cocaine"},
    {"code": "961.41(3g)(e)", "title": "Possession of Heroin", "category": "Drugs", "description": "Possession of heroin"},
    {"code": "961.41(3g)(g)", "title": "Possession of Methamphetamine", "category": "Drugs", "description": "Possession of methamphetamine"},
    {"code": "961.41(3i)", "title": "Possession of Drug Paraphernalia", "category": "Drugs", "description": "Possession of drug paraphernalia"},
    {"code": "961.42(1)", "title": "Possession of a Controlled Substance Without a Prescription", "category": "Drugs", "description": "Possession of a controlled substance not obtained by valid prescription"},
    {"code": "961.41(1)(am)", "title": "Manufacture/Deliver Schedule I or II Narcotic", "category": "Drugs", "description": "Manufactures or delivers a schedule I or II narcotic controlled substance"},
    {"code": "961.41(1)(e)", "title": "Manufacture/Deliver Amphetamine, LSD, or Psilocin", "category": "Drugs", "description": "Manufactures or delivers amphetamine, LSD, or psilocin"},
    {"code": "961.41(1)(g)", "title": "Manufacture/Deliver Schedule IV Controlled Substance", "category": "Drugs", "description": "Manufactures or delivers a schedule IV controlled substance"},
    {"code": "961.41(2)(e)", "title": "Possession of Amphetamine, LSD, or Psilocin", "category": "Drugs", "description": "Possession of amphetamine, LSD, or psilocin"},
    {"code": "961.455", "title": "Using a Child for Illegal Drug Distribution", "category": "Drugs", "description": "Intentionally uses a child to distribute or manufacture controlled substances"},
    {"code": "961.46", "title": "Distribution to Persons Under 18", "category": "Drugs", "description": "Distributes a controlled substance to a person under 18 years of age"},
    {"code": "346.63(1)(a)", "title": "Operating While Under the Influence (OWI) — 1st", "category": "Traffic", "description": "Operates a motor vehicle while under the influence of an intoxicant"},
    {"code": "346.63(1)(am)", "title": "Operating While Under the Influence (OWI) — PAC", "category": "Traffic", "description": "Operates a motor vehicle with a prohibited alcohol concentration"},
    {"code": "346.63(2)(a)", "title": "Operating While Under the Influence — Controlled Substance", "category": "Traffic", "description": "Operates a vehicle while under influence of a controlled substance"},
    {"code": "346.63(7)", "title": "Operating While Under the Influence — Cause Injury", "category": "Traffic", "description": "Operating while intoxicated causes injury to another"},
    {"code": "346.65(2)", "title": "OWI — 2nd Offense", "category": "Traffic", "description": "Second violation of operating while under the influence"},
    {"code": "346.65(3)", "title": "OWI — 3rd Offense", "category": "Traffic", "description": "Third violation of operating while under the influence"},
    {"code": "346.65(4)", "title": "OWI — 4th Offense", "category": "Traffic", "description": "Fourth or subsequent violation of operating while under the influence"},
    {"code": "346.67", "title": "Hit and Run — Attended Vehicle", "category": "Traffic", "description": "Duty to stop upon striking attended vehicle"},
    {"code": "346.68", "title": "Hit and Run — Unattended Vehicle", "category": "Traffic", "description": "Duty to stop upon striking unattended vehicle"},
    {"code": "346.04(3)", "title": "Fleeing or Eluding a Traffic Officer", "category": "Traffic", "description": "Intentionally flees or attempts to elude a traffic officer by direction or rate of speed"},
    {"code": "346.62", "title": "Reckless Driving", "category": "Traffic", "description": "Operates a vehicle in willful or wanton disregard for the safety of others"},
    {"code": "346.63(1)(b)", "title": "Operating While Under the Influence (OWI) — 1st (Drug Detection)", "category": "Traffic", "description": "Operates a motor vehicle while having a detectable amount of a restricted controlled substance in blood"},
    {"code": "346.63(2)(am)", "title": "Operating While Under the Influence — Controlled Substance (PAC)", "category": "Traffic", "description": "Operates a vehicle with a detectable amount of a restricted controlled substance"},
    {"code": "343.44", "title": "Operating After Revocation or Suspension", "category": "Traffic", "description": "Operates a motor vehicle while license is revoked or suspended"},
    {"code": "343.305(9)", "title": "Refusal to Submit to Chemical Testing", "category": "Traffic", "description": "Refuses to submit to a chemical test for intoxication"},
    {"code": "346.92", "title": "Speed Restrictions", "category": "Traffic", "description": "Operates a vehicle in excess of the speed limit"},
]

WI_JURY_INSTRUCTIONS = [
    {"code": "JI-101", "title": "Jury Instruction — Circumstantial Evidence", "category": "Evidence", "description": "Instructions on the use and weight of circumstantial evidence"},
    {"code": "JI-110", "title": "Jury Instruction — Credibility of Witnesses", "category": "Evidence", "description": "Factors jury may consider in weighing witness credibility"},
    {"code": "JI-115", "title": "Jury Instruction — Presumption of Innocence", "category": "Evidence", "description": "The defendant is presumed innocent throughout the trial"},
    {"code": "JI-120", "title": "Jury Instruction — Burden of Proof", "category": "Evidence", "description": "State must prove each element beyond a reasonable doubt"},
    {"code": "JI-140", "title": "Jury Instruction — Impeachment Evidence", "category": "Evidence", "description": "Use of prior inconsistent statements for impeachment purposes"},
    {"code": "JI-170", "title": "Jury Instruction — Expert Witness Testimony", "category": "Evidence", "description": "Lay and expert witness opinion testimony"},
    {"code": "JI-175", "title": "Jury Instruction — Consciousness of Guilt", "category": "Evidence", "description": "Evidence of flight or concealment may indicate consciousness of guilt"},
    {"code": "JI-180", "title": "Jury Instruction — Missing Witness", "category": "Evidence", "description": "Inference from failure to call a witness within party's control"},
    {"code": "JI-230", "title": "Jury Instruction — Unanimous Verdict", "category": "Procedure", "description": "Verdict must be unanimous"},
    {"code": "JI-250", "title": "Jury Instruction — Reasonable Doubt Defined", "category": "Procedure", "description": "Definition of reasonable doubt"},
    {"code": "JI-266", "title": "Jury Instruction — Multiple Defendants", "category": "Procedure", "description": "Each defendant entitled to separate consideration"},
    {"code": "JI-300", "title": "Jury Instruction — First-Degree Intentional Homicide Elements", "category": "Homicide", "description": "Elements of 940.01 — intent to kill, causation, death of victim"},
    {"code": "JI-310", "title": "Jury Instruction — First-Degree Reckless Homicide Elements", "category": "Homicide", "description": "Elements of 940.02 — reckless conduct, causation, death"},
    {"code": "JI-320", "title": "Jury Instruction — Second-Degree Reckless Homicide Elements", "category": "Homicide", "description": "Elements of 940.06 — criminally reckless conduct"},
    {"code": "JI-330", "title": "Jury Instruction — Homicide by Intoxicated Use of Vehicle", "category": "Homicide", "description": "Elements of 940.09 — OWI causing death"},
    {"code": "JI-350", "title": "Jury Instruction — Battery Elements", "category": "Assault", "description": "Elements of 940.60(1) — intent to cause bodily harm"},
    {"code": "JI-355", "title": "Jury Instruction — Substantial Battery Elements", "category": "Assault", "description": "Elements of 940.60(2) — substantial bodily harm"},
    {"code": "JI-400", "title": "Jury Instruction — First-Degree Sexual Assault Elements", "category": "Sexual Assault", "description": "Elements of 940.225(1)"},
    {"code": "JI-410", "title": "Jury Instruction — Second-Degree Sexual Assault Elements", "category": "Sexual Assault", "description": "Elements of 940.225(2)"},
    {"code": "JI-420", "title": "Jury Instruction — Third-Degree Sexual Assault Elements", "category": "Sexual Assault", "description": "Elements of 940.225(3)"},
    {"code": "JI-430", "title": "Jury Instruction — Fourth-Degree Sexual Assault Elements", "category": "Sexual Assault", "description": "Elements of 940.225(4)"},
    {"code": "JI-500", "title": "Jury Instruction — Burglary Elements", "category": "Burglary", "description": "Elements of 943.10(1)"},
    {"code": "JI-505", "title": "Jury Instruction — Criminal Trespass Elements", "category": "Burglary", "description": "Elements of 943.14"},
    {"code": "JI-520", "title": "Jury Instruction — Theft Elements", "category": "Theft", "description": "Elements of 943.20(1)"},
    {"code": "JI-530", "title": "Jury Instruction — Robbery Elements", "category": "Robbery", "description": "Elements of 943.32(1)"},
    {"code": "JI-535", "title": "Jury Instruction — Armed Robbery Elements", "category": "Robbery", "description": "Elements of 943.32(2)"},
    {"code": "JI-540", "title": "Jury Instruction — Receiving Stolen Property Elements", "category": "Theft", "description": "Elements of 943.34(1)"},
    {"code": "JI-560", "title": "Jury Instruction — Identity Theft Elements", "category": "Fraud", "description": "Elements of 943.201"},
    {"code": "JI-620", "title": "Jury Instruction — Bail Jumping Elements", "category": "Public Order", "description": "Elements of 946.49(1)"},
    {"code": "JI-625", "title": "Jury Instruction — Resisting or Obstructing Officer Elements", "category": "Public Order", "description": "Elements of 946.41"},
    {"code": "JI-630", "title": "Jury Instruction — Disorderly Conduct Elements", "category": "Public Order", "description": "Elements of 947.01"},
    {"code": "JI-635", "title": "Jury Instruction — Harassment Elements", "category": "Public Order", "description": "Elements of 947.013"},
    {"code": "JI-650", "title": "Jury Instruction — First-Degree Sexual Assault of a Child Elements", "category": "Child Protection", "description": "Elements of 948.02(1)"},
    {"code": "JI-660", "title": "Jury Instruction — Child Enticement Elements", "category": "Child Protection", "description": "Elements of 948.07"},
    {"code": "JI-700", "title": "Jury Instruction — Possession of Cocaine Elements", "category": "Drugs", "description": "Elements of 961.41(3g)(c) — knowing possession"},
    {"code": "JI-710", "title": "Jury Instruction — Manufacture/Deliver Cocaine Elements", "category": "Drugs", "description": "Elements of 961.41(1)(cm)"},
    {"code": "JI-720", "title": "Jury Instruction — Possession of Marijuana Elements", "category": "Drugs", "description": "Elements of 961.41(2)(g)"},
    {"code": "JI-800", "title": "Jury Instruction — OWI Elements", "category": "Traffic", "description": "Elements of 346.63(1)(a) — operating, intoxication, on a highway"},
    {"code": "JI-810", "title": "Jury Instruction — Hit and Run Elements", "category": "Traffic", "description": "Elements of 346.67"},
    {"code": "JI-820", "title": "Jury Instruction — Fleeing/Eluding Officer Elements", "category": "Traffic", "description": "Elements of 346.04(3)"},
    {"code": "JI-900", "title": "Jury Instruction — Intoxication as Defense", "category": "Defenses", "description": "Voluntary intoxication is not a defense to criminal intent"},
    {"code": "JI-905", "title": "Jury Instruction — Self-Defense", "category": "Defenses", "description": "Use of force in self-defense"},
    {"code": "JI-910", "title": "Jury Instruction — Defense of Others", "category": "Defenses", "description": "Use of force to defend a third person"},
    {"code": "JI-915", "title": "Jury Instruction — Defense of Property", "category": "Defenses", "description": "Use of force to defend property"},
    {"code": "JI-315", "title": "Jury Instruction — Second-Degree Intentional Homicide Elements", "category": "Homicide", "description": "Elements of 940.05 — intent to kill, causation, death of victim"},
    {"code": "JI-335", "title": "Jury Instruction — Felony Murder Elements", "category": "Homicide", "description": "Elements of 940.03 — causing death while committing a felony"},
    {"code": "JI-336", "title": "Jury Instruction — Homicide by Negligent Handling of Dangerous Weapon Elements", "category": "Homicide", "description": "Elements of 940.08 — negligent handling, causation, death"},
    {"code": "JI-337", "title": "Jury Instruction — Mutilating or Hiding a Corpse Elements", "category": "Homicide", "description": "Elements of 940.11 — mutilation, dismemberment, or concealment with intent to conceal a crime"},
    {"code": "JI-360", "title": "Jury Instruction — Reckless Injury Elements", "category": "Assault", "description": "Elements of 940.23 — reckless conduct causing great bodily harm"},
    {"code": "JI-361", "title": "Jury Instruction — Strangulation and Suffocation Elements", "category": "Assault", "description": "Elements of 940.235 — intentional strangulation or suffocation"},
    {"code": "JI-365", "title": "Jury Instruction — Human Trafficking Elements", "category": "Assault", "description": "Elements of 940.302 — recruitment or transportation for forced labor or commercial sex"},
    {"code": "JI-370", "title": "Jury Instruction — Stalking Elements", "category": "Public Order", "description": "Elements of 940.32 — course of conduct causing serious emotional distress or fear"},
    {"code": "JI-440", "title": "Jury Instruction — Invasion of Privacy Elements", "category": "Public Order", "description": "Elements of 942.08 — viewing or recording a nude person without consent in a private place"},
    {"code": "JI-445", "title": "Jury Instruction — Revenge Porn Elements", "category": "Public Order", "description": "Elements of 942.09 — posting or distributing nude representations without consent"},
    {"code": "JI-450", "title": "Jury Instruction — Criminal Damage to Property Elements", "category": "Crimes Against Property", "description": "Elements of 943.01 — intentional damage to property of another"},
    {"code": "JI-455", "title": "Jury Instruction — Arson of Buildings Elements", "category": "Crimes Against Property", "description": "Elements of 943.02 — intentional burning of a building"},
    {"code": "JI-460", "title": "Jury Instruction — Carjacking Elements", "category": "Robbery", "description": "Elements of 943.231 — taking a motor vehicle by force or threat of force"},
    {"code": "JI-465", "title": "Jury Instruction — Issue of Worthless Check Elements", "category": "Fraud", "description": "Elements of 943.24 — issuing a check on insufficient funds with intent to defraud"},
    {"code": "JI-510", "title": "Jury Instruction — Possession of Burglarious Tools Elements", "category": "Burglary", "description": "Elements of 943.12 — possession of tools with intent to commit burglary"},
    {"code": "JI-515", "title": "Jury Instruction — Entry Into Locked Vehicle Elements", "category": "Burglary", "description": "Elements of 943.11 — intentional entry into a locked vehicle without consent"},
    {"code": "JI-570", "title": "Jury Instruction — Theft of Mail Elements", "category": "Theft", "description": "Elements of 943.204 — taking mail from a mail receptacle without consent"},
    {"code": "JI-600", "title": "Jury Instruction — Bestiality Elements", "category": "Sex Offenses", "description": "Elements of 944.18 — sexual penetration or contact with an animal"},
    {"code": "JI-605", "title": "Jury Instruction — Lewd and Lascivious Behavior Elements", "category": "Sex Offenses", "description": "Elements of 944.20 — lewd or indecent act in public"},
    {"code": "JI-610", "title": "Jury Instruction — Obscene Electronic Messages Elements", "category": "Sex Offenses", "description": "Elements of 944.25 — sending obscene or sexually explicit electronic messages"},
    {"code": "JI-615", "title": "Jury Instruction — Patronizing Prostitutes Elements", "category": "Sex Offenses", "description": "Elements of 944.31 — hiring a person for sexual acts for a fee"},
    {"code": "JI-618", "title": "Jury Instruction — Pandering Elements", "category": "Sex Offenses", "description": "Elements of 944.33 — compelling another to become a prostitute"},
    {"code": "JI-640", "title": "Jury Instruction — Swatting Elements", "category": "Public Order", "description": "Elements of 947.014 — false report of an emergency causing a law enforcement response"},
    {"code": "JI-641", "title": "Jury Instruction — Bomb Scare Elements", "category": "Public Order", "description": "Elements of 947.015 — false report of a bomb or explosive"},
    {"code": "JI-642", "title": "Jury Instruction — Threatening Bodily Harm Elements", "category": "Public Order", "description": "Elements of 947.016 — threat to cause bodily harm to another"},
    {"code": "JI-643", "title": "Jury Instruction — Terrorist Threats Elements", "category": "Public Order", "description": "Elements of 947.019 — threat to commit an act of terrorism"},
    {"code": "JI-645", "title": "Jury Instruction — Bribery of Public Officers Elements", "category": "Public Order", "description": "Elements of 946.10 — offering a bribe to influence official action"},
    {"code": "JI-646", "title": "Jury Instruction — Misconduct in Public Office Elements", "category": "Public Order", "description": "Elements of 946.12 — excess of lawful authority with intent to gain benefit or harm"},
    {"code": "JI-647", "title": "Jury Instruction — Perjury Elements", "category": "Public Order", "description": "Elements of 946.31 — false statement under oath"},
    {"code": "JI-648", "title": "Jury Instruction — Obstructing Justice Elements", "category": "Public Order", "description": "Elements of 946.65 — intentionally obstructing the administration of justice"},
    {"code": "JI-649", "title": "Jury Instruction — Impersonating a Public Officer Elements", "category": "Public Order", "description": "Elements of 946.69 — falsely assuming to act as a public officer"},
    {"code": "JI-655", "title": "Jury Instruction — Failure to Submit DNA Elements", "category": "Public Order", "description": "Elements of 946.52 — failure to provide a biological specimen for DNA analysis"},
    {"code": "JI-658", "title": "Jury Instruction — Intimidation of Witnesses Elements", "category": "Public Order", "description": "Elements of 940.42 — threatening or intimidating a witness"},
    {"code": "JI-659", "title": "Jury Instruction — Duty to Aid Elements", "category": "Public Order", "description": "Elements of 940.34 — failure to give aid or report a crime involving bodily harm"},
    {"code": "JI-670", "title": "Jury Instruction — Sexual Exploitation of a Child Elements", "category": "Child Protection", "description": "Elements of 948.05 — permitting or causing a child to engage in sexually explicit conduct"},
    {"code": "JI-671", "title": "Jury Instruction — Trafficking of a Child Elements", "category": "Child Protection", "description": "Elements of 948.051 — recruiting or transporting a child for forced labor or commercial sex"},
    {"code": "JI-672", "title": "Jury Instruction — Grooming a Child for Sexual Activity Elements", "category": "Child Protection", "description": "Elements of 948.072 — course of conduct to prepare a child for sexual activity"},
    {"code": "JI-673", "title": "Jury Instruction — Computer Facilitated Child Sex Crime Elements", "category": "Child Protection", "description": "Elements of 948.075 — using a computer to facilitate a sex crime against a child"},
    {"code": "JI-674", "title": "Jury Instruction — Possession of Child Pornography Elements", "category": "Child Protection", "description": "Elements of 948.12 — knowing possession of child pornography"},
    {"code": "JI-675", "title": "Jury Instruction — Abandonment of a Child Elements", "category": "Child Protection", "description": "Elements of 948.20 — intentional abandonment of a child under 18"},
    {"code": "JI-676", "title": "Jury Instruction — Neglecting a Child Elements", "category": "Child Protection", "description": "Elements of 948.21 — intentional failure to provide necessary care for a child"},
    {"code": "JI-677", "title": "Jury Instruction — Abduction of Another's Child Elements", "category": "Child Protection", "description": "Elements of 948.30 — taking another's child with intent to keep or conceal"},
    {"code": "JI-730", "title": "Jury Instruction — Manufacture/Deliver Schedule I or II Narcotic Elements", "category": "Drugs", "description": "Elements of 961.41(1)(am) — manufacturing or delivering a schedule I or II narcotic"},
    {"code": "JI-740", "title": "Jury Instruction — Possession of Amphetamine Elements", "category": "Drugs", "description": "Elements of 961.41(2)(e) — knowing possession of amphetamine, LSD, or psilocin"},
    {"code": "JI-750", "title": "Jury Instruction — Using Child for Drug Distribution Elements", "category": "Drugs", "description": "Elements of 961.455 — intentionally using a child to distribute or manufacture drugs"},
    {"code": "JI-830", "title": "Jury Instruction — Operating After Revocation Elements", "category": "Traffic", "description": "Elements of 343.44 — operating a motor vehicle while license revoked or suspended"},
    {"code": "JI-835", "title": "Jury Instruction — Refusal to Submit to Chemical Test Elements", "category": "Traffic", "description": "Elements of 343.305(9) — refusing to submit to a chemical test for intoxication"},
    {"code": "JI-840", "title": "Jury Instruction — Reckless Driving Elements", "category": "Traffic", "description": "Elements of 346.62 — willful or wanton disregard for safety while driving"},
    {"code": "JI-845", "title": "Jury Instruction — Speeding Elements", "category": "Traffic", "description": "Elements of 346.92 — operating a vehicle in excess of the speed limit"},
    {"code": "JI-860", "title": "Jury Instruction — Mistreating Animals Elements", "category": "Crimes Against Property", "description": "Elements of 951.02 — treating an animal in a cruel manner"},
    {"code": "JI-865", "title": "Jury Instruction — Dogfighting Elements", "category": "Crimes Against Property", "description": "Elements of 951.08 — causing or permitting animals to fight for amusement or gain"},
    {"code": "JI-870", "title": "Jury Instruction — Harassment of Police Dog Elements", "category": "Public Order", "description": "Elements of 951.095 — intentionally harming or interfering with a police, fire, or search and rescue dog"},
]

WI_TITLE_CHAPTER_MAP = {
    "940": "Crimes Against Life and Bodily Security (Ch. 940)",
    "941": "Crimes Against Public Health and Safety (Ch. 941)",
    "942": "Crimes Against Reputation and Privacy (Ch. 942)",
    "943": "Crimes Against Property (Ch. 943)",
    "944": "Crimes Against Sexual Morality (Ch. 944)",
    "945": "Gambling (Ch. 945)",
    "946": "Crimes Against Government (Ch. 946)",
    "947": "Crimes Against Public Peace (Ch. 947)",
    "948": "Crimes Against Children (Ch. 948)",
    "951": "Crimes Against Animals (Ch. 951)",
    "961": "Controlled Substances (Ch. 961)",
    "346": "Traffic Regulations (Ch. 346)",
    "347": "Vehicle Equipment (Ch. 347)",
    "350": "Snowmobiles and ATVs (Ch. 350)",
    "351": "Motor Vehicle Theft (Ch. 351)",
}


def search_statutes(query: str, limit: int = 10) -> List[Dict]:
    if not query:
        return []
    results = []
    q = query.lower()
    for s in WI_CRIMINAL_STATUTES:
        if q in s["code"].lower() or q in s["title"].lower() or q in s["category"].lower():
            results.append(s)
            if len(results) >= limit:
                break
    if not results:
        for s in WI_CRIMINAL_STATUTES:
            if q in s.get("description", "").lower():
                results.append(s)
                if len(results) >= limit:
                    break
    return results


def search_jury_instructions(query: str, limit: int = 10) -> List[Dict]:
    if not query:
        return []
    results = []
    q = query.lower()
    for ji in WI_JURY_INSTRUCTIONS:
        if q in ji["code"].lower() or q in ji["title"].lower() or q in ji["category"].lower():
            results.append(ji)
            if len(results) >= limit:
                break
    if not results:
        for ji in WI_JURY_INSTRUCTIONS:
            if q in ji.get("description", "").lower():
                results.append(ji)
                if len(results) >= limit:
                    break
    return results


def get_statute(code: str) -> Optional[Dict]:
    for s in WI_CRIMINAL_STATUTES:
        if s["code"] == code:
            return s
    return None


def get_jury_instruction(code: str) -> Optional[Dict]:
    for ji in WI_JURY_INSTRUCTIONS:
        if ji["code"] == code:
            return ji
    return None


def get_chapter_title(code_prefix: str) -> str:
    return WI_TITLE_CHAPTER_MAP.get(code_prefix, "Other")


def statutes_by_category(category: str, limit: int = 20) -> List[Dict]:
    return [s for s in WI_CRIMINAL_STATUTES if s["category"].lower() == category.lower()][:limit]


def all_categories() -> List[str]:
    cats = set()
    for s in WI_CRIMINAL_STATUTES:
        cats.add(s["category"])
    return sorted(cats)


REPORT_TYPE_CATEGORIES = {
    "Standard Incident Report": ["Homicide", "Assault", "Sexual Assault", "Burglary", "Theft",
                                  "Robbery", "Fraud", "Weapons", "Drugs", "Public Order", "Child Protection"],
    "Search Warrant Affidavit": ["Homicide", "Assault", "Sexual Assault", "Burglary", "Theft",
                                 "Robbery", "Fraud", "Weapons", "Drugs", "Child Protection"],
    "Internal Use-of-Force Review": ["Assault", "Weapons", "Public Order"],
    "OWI / DUI Report": ["Traffic", "Homicide"],
}


def statutes_for_report_type(report_type: str) -> List[Dict]:
    categories = REPORT_TYPE_CATEGORIES.get(report_type, [])
    results = []
    seen = set()
    for s in WI_CRIMINAL_STATUTES:
        if s["category"] in categories and s["code"] not in seen:
            results.append(s)
            seen.add(s["code"])
    return results


def format_statutes_for_prompt(statutes: List[Dict]) -> str:
    if not statutes:
        return ""
    lines = ["\n--- APPLICABLE WISCONSIN STATUTES ---"]
    for s in statutes:
        desc = s.get("description", "")
        lines.append(f"- {s['code']} {s['title']}: {desc}")
    lines.append("--- END STATUTES ---\n")
    return "\n".join(lines)


if __name__ == '__main__':
    print(f"Loaded {len(WI_CRIMINAL_STATUTES)} Wisconsin criminal statutes")
    print(f"Loaded {len(WI_JURY_INSTRUCTIONS)} jury instructions")
    print(f"Categories: {all_categories()}")
    for q in ["homicide", "940.01", "theft"]:
        print(f"\nSearch '{q}':", [s["code"] for s in search_statutes(q)])
