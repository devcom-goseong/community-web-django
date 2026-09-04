"""Copy for the seven activities. Imported by seed_content."""

ACTIVITIES = [
    {
        "slug": "community-meeting",
        "name": "The community meeting",
        "cadence": "Weekly",
        "primary": True,
        "summary": "One meeting a week with a chosen topic, member updates and a rotating "
                   "moderator. It is the spine everything else in the community hangs from.",
        "body": "One meeting a week, and it is the spine everything else hangs from. Each week "
                "has a chosen topic — artificial intelligence one week, Python the next, web "
                "development after that. A moderator guides the discussion so it stays "
                "organised, and the moderator changes from week to week so it never becomes one "
                "person's show.\n\n"
                "The point is that it is interactive, not a lecture. Half of the value is in the "
                "part where members talk about their own week.",
        "index_bullets": "A topic selected for each meeting\n"
                         "Members share what they learned that week\n"
                         "What they are working on right now\n"
                         "A problem they are trying to solve\n"
                         "A project they want feedback on\n"
                         "Guest speakers when we can invite them",
        "sections": [
            {"heading": "What it is",
             "body": "One meeting a week, every week. It is the only thing we ask people to try "
                     "to keep, because everything else grows out of the conversations that happen "
                     "in it.\n\nEach week has a chosen topic. The topic gives the meeting a spine, "
                     "but it is not a lecture and nobody is expected to have prepared."},
            {"heading": "How an hour runs",
             "bullets": "A short introduction to the week's topic, by whoever proposed it.\n"
                        "Open discussion on that topic. Questions at any level are fine.\n"
                        "Member updates — what people learned, are building, or are stuck on.\n"
                        "Anything the community needs to decide together."},
            {"heading": "The moderator changes every week",
             "body": "Someone different guides the discussion each time. This is deliberate. A "
                     "meeting with a permanent host becomes that person's meeting, and everyone "
                     "else becomes an audience. Rotating it keeps the room shared, and it gives "
                     "people practice at running a conversation.\n\nYou are not expected to "
                     "volunteer in your first weeks, and nobody is put on the spot."},
            {"heading": "Guest speakers",
             "body": "When we can arrange it, we invite someone in — a developer, a researcher, a "
                     "student further along than us, or someone working in industry. They join the "
                     "discussion rather than presenting at it. If you know somebody worth "
                     "inviting, say so."},
            {"heading": "Member updates are the point",
             "body": "The half of the meeting where members talk about their own week is the half "
                     "that matters most. It is how people find out who is working on what, and it "
                     "is how project teams end up forming. What you share can be small.",
             "bullets": "Something you learned\nSomething you are building\n"
                        "Something you discovered and thought was interesting\n"
                        "A problem you cannot solve\nA project you want honest feedback on",
             "columns": True},
            {"heading": "If you cannot come",
             "body": "Say so in the channel, and read what gets posted afterwards. Missing a "
                     "meeting is not a problem. Disappearing without a word for a month is what "
                     "makes a community hard to run."},
        ],
    },
    {
        "slug": "study-groups",
        "name": "Study groups",
        "cadence": "Weekly",
        "extra_tag": "Member-run",
        "summary": "Small groups learning one subject together. You do not need permission to "
                   "start one, and certification preparation works especially well this way.",
        "body": "Small groups learning one subject together. You do not need the leadership "
                "team's permission to start one — pick a subject, find two or three other people, "
                "agree a time. Members create and manage the groups around whatever they are "
                "actually interested in.\n\n"
                "Certification preparation works especially well this way. People studying for a "
                "cloud certification can work through it together, share resources and keep each "
                "other consistent, which is the part most people fail at alone.",
        "index_bullets": "Programming\nData science\nWeb development\nMobile development\n"
                         "Certification preparation\nWhatever else people want to study",
        "sections": [
            {"heading": "What it is",
             "body": "A handful of people learning the same thing at the same time, meeting on a "
                     "fixed schedule they set themselves. Study groups are run by members, not by "
                     "the leadership team."},
            {"heading": "Starting one",
             "body": "You do not need permission and you do not need to be an expert in the "
                     "subject. Wanting to learn it is the qualification.",
             "bullets": "Pick a subject specific enough to finish something in it.\n"
                        "Find two or three other people. Post it at the meeting or in the channel.\n"
                        "Agree a time and keep it. A fixed weekly slot survives; finding a time each week does not.\n"
                        "Decide what you are working through — a course, a book, a syllabus, a project."},
            {"heading": "Subjects people are studying",
             "bullets": "Programming fundamentals\nData science\nWeb development\n"
                        "Mobile development\nCloud certifications\nAnything else with two or three takers",
             "columns": True},
            {"heading": "Why certifications work well in a group",
             "body": "Certification syllabuses are long, dry, and easy to abandon in week three. "
                     "In a group the material gets split up, someone explains the part you did not "
                     "understand, and there is a mild social cost to not doing the reading. That "
                     "last part is doing most of the work, and it is the part you cannot get alone."},
            {"heading": "If a group stops",
             "body": "Some do. Exams arrive, interest moves, people get busy. A study group that "
                     "ran for six weeks and then stopped was not a failure; it was six weeks of "
                     "studying you would not otherwise have done. Say it has finished so nobody is "
                     "left wondering, and start another one when you want to."},
        ],
    },
    {
        "slug": "ideas",
        "name": "Idea submissions",
        "cadence": "Always open",
        "primary": True,
        "summary": "Anywhere an idea can be submitted, because good ideas come from anyone. "
                   "Here is what happens to one after you send it.",
        "body": "There is somewhere to put an idea, because good ideas come from anyone — "
                "including people who joined last week. Members can submit projects, workshops, "
                "events, competitions, community improvements, new study groups, problems they "
                "want to solve, or opportunities to collaborate.\n\n"
                "An idea does not automatically become a community project just because somebody "
                "suggested it. The leadership team reviews submissions against a short, honest set "
                "of questions, and says so either way.",
        "sections": [
            {"heading": "What it is",
             "body": "A place to put an idea, open to every member from the day they join. Good "
                     "ideas come from anyone, including people who arrived last week and are "
                     "looking at the community with fresh eyes."},
            {"heading": "What you can submit",
             "bullets": "A project you want built\nA workshop you want run\nAn event\n"
                        "A competition to enter\nA new study group\nA problem worth solving\n"
                        "Something the community should do better\nA collaboration outside it",
             "columns": True},
            {"heading": "What happens next",
             "body": "The leadership team reads it and answers you either way. An idea does not "
                     "automatically become a community project because somebody suggested it — "
                     "that is the difference between a community with a direction and a list of "
                     "abandoned repositories."},
            {"heading": "The questions an idea gets asked",
             "note_title": "The questions an idea gets asked",
             "bullets": "Is it realistic?\nDo we have people who can work on it?\n"
                        "What resources would it need?\nWho would benefit from it?\n"
                        "Does it fit the community?\nCan it be finished in a reasonable time?",
             "columns": True},
            {"heading": "The three answers",
             "bullets": "Yes. It becomes a project, an event or a group, and we find people for it.\n"
                        "Not yet. Good, but we lack the people or the time. It stays on the list.\n"
                        "No. With a reason. A clear no is more useful than silence.",
             },
        ],
    },
    {
        "slug": "projects",
        "name": "Project teams",
        "cadence": "Ongoing",
        "summary": "Members finding people whose skills complete theirs and building something "
                   "that exists outside a tutorial.",
        "body": "Members find people whose skills complete their own and build something real. "
                "One project might need a programmer, a designer, someone who understands AI, "
                "someone responsible for documentation, and someone interested in the business or "
                "marketing side.\n\n"
                "This is exactly why the community is not limited to programmers. The goal is to "
                "give students genuine experience of working in a team and producing something "
                "that exists when you close the laptop.",
        "sections": [
            {"heading": "What it is",
             "body": "Small teams building something real. The goal is not a perfect product — it "
                     "is the experience of working with other people towards something that still "
                     "exists when you close the laptop."},
            {"heading": "A project needs more than a programmer",
             "body": "This is the single biggest reason the community is not limited to people who "
                     "write code. A project that only has engineers on it usually produces "
                     "something that works and that nobody can use.",
             "bullets": "Someone who writes the code\n"
                        "Someone who designs how it looks and behaves\n"
                        "Someone who understands the data or the AI part, if there is one\n"
                        "Someone who keeps the documentation honest\n"
                        "Someone thinking about who it is for\n"
                        "Someone keeping the team organised"},
            {"heading": "How teams form",
             "body": "Usually at the weekly meeting. Someone describes what they want to build, "
                     "other people say what they could contribute, and a team either forms or it "
                     "does not. An idea that nobody volunteers for is telling you something useful."},
            {"heading": "Agree responsibilities on day one",
             "body": "Before any work starts, write down who is doing what and roughly by when. "
                     "Most student projects do not collapse for technical reasons. They collapse "
                     "because three people each assumed somebody else was doing the part nobody "
                     "did.\n\nIf you cannot deliver your part, say so early. That is normal, and it "
                     "is only a problem when it is discovered late."},
            {"heading": "Finishing",
             "body": "Demo day is the natural deadline: a fixed date, an audience, and something to "
                     "show. Projects that never have a deadline tend never to have an ending either."},
        ],
    },
    {
        "slug": "hackathons",
        "name": "Hackathons and competitions",
        "cadence": "When they come up",
        "summary": "Internal events, external hackathons, online challenges and university "
                   "competitions. At the start the priority is taking part, not winning.",
        "body": "We organise and take part in hackathons. At the start the priority is "
                "participation and learning rather than winning — the experience of building under "
                "a deadline with people you have just met is the point. As the community gets more "
                "experienced, we run larger events ourselves.",
        "index_bullets": "Internal KDU hackathons\nExternal hackathons\nOnline challenges\n"
                         "University competitions\nTechnology competitions\nIndustry-run challenges",
        "sections": [
            {"heading": "What it is",
             "body": "Building something under a deadline, usually over a day or a weekend, "
                     "usually with people you have just met. It is intense, slightly chaotic, and "
                     "one of the fastest ways to find out what you can actually do."},
            {"heading": "What we take part in",
             "bullets": "Internal KDU hackathons\nExternal hackathons\nOnline challenges\n"
                        "University competitions\nTechnology competitions\nIndustry-run challenges",
             "columns": True},
            {"heading": "Participation first, winning later",
             "body": "At the beginning the point is to take part and learn how these events work. "
                     "Teams that have never entered one before do not win them, and treating the "
                     "first few as practice is the honest way to approach it."},
            {"heading": "If you have never done one",
             "bullets": "You do not need to be good yet. Every team needs someone to test things and prepare the presentation.\n"
                        "Scope down hard. The teams that finish build one small thing properly.\n"
                        "Sleep. The all-nighter is a myth that produces broken demos.\n"
                        "Prepare the presentation before you think you need to."},
            {"heading": "How teams are chosen",
             "body": "We announce an event in the channel, people say whether they want in, and "
                     "teams form around who is available. Nobody is picked or left out by the "
                     "leadership team."},
        ],
    },
    {
        "slug": "demo-day",
        "name": "Demo day",
        "cadence": "Once a term",
        "summary": "Members present what they have been building to the rest of the community, "
                   "and get honest feedback on it.",
        "body": "Members present the projects they have been working on to the rest of the "
                "community. It is deliberately a little uncomfortable, because presenting your own "
                "work is a skill and the only way to get it is to do it.",
        "index_bullets": "Present what you built\nReceive real feedback\n"
                         "Practise communicating your work\nBuild confidence\nShow your portfolio\n"
                         "Find people to collaborate with next",
        "sections": [
            {"heading": "What it is",
             "body": "Once a term, everyone who has been working on something presents it to the "
                     "rest of the community. Short presentations, questions afterwards, no marks "
                     "and no prizes."},
            {"heading": "It is deliberately a little uncomfortable",
             "body": "Presenting your own work is a skill, and the only way to acquire it is to do "
                     "it in front of people. Almost everybody finds the first one unpleasant. "
                     "Almost everybody finds the third one fine. That progression is the entire "
                     "point of the event."},
            {"heading": "What you get out of it",
             "bullets": "Practice at explaining technical work to people who did not build it\n"
                        "Feedback from people who are not your friends being polite about it\n"
                        "A portfolio piece you have actually talked through\n"
                        "Confidence, which arrives afterwards rather than before\n"
                        "Collaborators — a lot of second projects start on demo day"},
            {"heading": "What to present",
             "body": "Anything you have worked on. It does not have to be finished, and it does "
                     "not have to have worked. A five-minute talk on something that failed and what "
                     "you learned from it is more useful to the room than a polished demo of a "
                     "tutorial project."},
            {"heading": "Preparing",
             "bullets": "Say what it is and who it is for in the first thirty seconds.\n"
                        "Show the thing working before you explain how it works.\n"
                        "Be honest about what is broken. Everyone in the room has broken things.\n"
                        "Practise once out loud. Once is enough."},
        ],
    },
    {
        "slug": "meetups",
        "name": "In-person meetups",
        "cadence": "Monthly",
        "primary": True,
        "extra_tag": "In person",
        "summary": "At least one physical meeting a month, for workshops, hands-on sessions and "
                   "the kind of conversation that does not happen in a chat window.",
        "body": "Most of what we do happens online, but a community that only exists in a chat "
                "window is not much of a community. At least once a month we meet physically — for "
                "coding workshops, hands-on sessions, project work, guest speakers, or simply to "
                "talk to each other properly.",
        "sections": [
            {"heading": "What it is",
             "body": "Most of what the community does happens online, and that is what makes it "
                     "possible for people outside the university to take part. But a community "
                     "that only exists in a chat window is not much of a community, so we meet "
                     "physically at least once a month."},
            {"heading": "What happens at one",
             "bullets": "Coding workshops\nHands-on sessions\nProject work, in the same room\n"
                        "Guest speakers\nCommunity discussions\nTalking to people properly",
             "columns": True},
            {"heading": "If it is your first",
             "body": "Turn up and say you are new. That is the whole protocol. You do not need to "
                     "bring anything, know anyone, or have something to show. Bring a laptop if "
                     "there is a workshop; otherwise do not worry about it."},
            {"heading": "Where and when",
             "body": "The location and schedule depend on availability and on arrangements with "
                     "the university, so they are announced in advance on the community platform "
                     "rather than fixed here. If a date does not work for most people, we move it."},
            {"heading": "If you are not in Goseong",
             "note_title": "If you are not in Goseong",
             "body": "Members outside the university — and outside Korea — are not expected at the "
                     "in-person meetups. Everything else runs online, and where a meetup has a "
                     "workshop or a guest speaker worth sharing, we try to make that part joinable "
                     "remotely."},
        ],
    },
]
