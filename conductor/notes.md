u9802715831@id.gle
g5-admin-test@test.com


0
/home/dima/dev/vexa-agentic-runtime/features/bot-lifecycle
/home/dima/dev/vexa-agentic-runtime/features/webhooks
/home/dima/dev/vexa-agentic-runtime/features/auth-and-limits
/home/dima/dev/vexa-agentic-runtime/features/schema-sync 
/home/dima/dev/vexa-agentic-runtime/features/post-meeting-transcription
/home/dima/dev/vexa-agentic-runtime/features/realtime-transcription
/home/dima/dev/vexa-agentic-runtime/features/chat
/home/dima/dev/vexa-agentic-runtime/features/remote-browser
/home/dima/dev/vexa-agentic-runtime/features/speaking-bot
/home/dima/dev/vexa-agentic-runtime/features/bot-escalation

container lfecycle


1
meeting-api refactoring

/home/dima/dev/vexa-agentic-runtime/features/mcp-integration
/home/dima/dev/vexa-agentic-runtime/features/multi-platform +














2
/home/dima/dev/vexa-agentic-runtime/features/scheduler
/home/dima/dev/vexa-agentic-runtime/features/calendar-integration


3
/home/dima/dev/vexa-agentic-runtime/features/agentic-runtime
/home/dima/dev/vexa-agentic-runtime/features/knowledge-workspace
/home/dima/dev/vexa-agentic-runtime/features/meeting-aware-agent
/home/dima/dev/vexa-agentic-runtime/features/telegram-chat
/home/dima/dev/vexa-agentic-runtime/features/tools
/home/dima/dev/vexa-agentic-runtime/features/video-recording





❯ now take a look here. We will be refactoring this feature and the related code to fix the issues related to the bot lifecycle.


  what is super important abou this one is soething that must be lcearly stated in the  readmes and implemented in code:


  let's think of the key requirements here


  A. decalarative user defined bot state

  1. explisit action by user to stop bot isdeclarative - it updates the meeting state in the database.

  2. Database state is the source of truth


  why like that? We have max confucfent bots limit and that limit must respect actual user detision to have a bot, not - the container state. COntainer state is teh runtime API responsibility. Meeting API does not care - it limits user to request more bots than
  allowed. But user stop action is decl;aratibve


  B. Bots need to have user defined bot time on meeting and max time left alone and max wait for admission. With defaults to me 2 hours, 15 min and 15 min.  Those ned to be user managed.

  THis is to make sure no zombie bots there.

  This params set via meeitng api and update user:data field


  we probably want to use runtime api scheduler for max bot live and use bot internal timeout to stop by the two other things