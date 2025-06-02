import os
import collections
import collections.abc
collections.Mapping = collections.abc.Mapping

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    ConversationHandler, MessageHandler, filters, ContextTypes
)
from experta import *

# مراحل الحوار
GOAL, LEVEL, WEIGHT, SUPPLEMENTS = range(4)
user_data = {}

# قواعد خبير التغذية
class PrimaryGoal(Fact): type = Field(str)
class ExperienceLevel(Fact): level = Field(str)
class BodyWeight(Fact): kg = Field(float)
class WantsSupplementInfo(Fact): status = Field(bool)
class AdviceGiven(Fact): type = Field(str)

class FitnessExpert(KnowledgeEngine):
    def __init__(self):
        super().__init__()
        self.responses = []

    @DefFacts()
    def startup(self):
        yield Fact(start=True)

    @Rule(PrimaryGoal(type=MATCH.goal), NOT(AdviceGiven(type='calories')))
    def advise_calories(self, goal):
        msg = {
            "muscle_gain": "✅ زد السعرات بنسبة بسيطة لتحقيق نمو عضلي.",
            "fat_loss": "✅ قلل السعرات بشكل مدروس لتخفيض الدهون.",
            "strength_increase": "✅ تناول سعرات قريبة من احتياجك لزيادة القوة.",
            "general_fitness": "✅ وازن السعرات للحفاظ على اللياقة."
        }.get(goal, "")
        self.responses.append(msg)
        self.declare(AdviceGiven(type='calories'))

    @Rule(PrimaryGoal(type=MATCH.goal), BodyWeight(kg=MATCH.kg), NOT(AdviceGiven(type='protein')))
    def advise_protein(self, goal, kg):
        if goal == "fat_loss":
            low, high = kg * 1.8, kg * 2.5
        elif goal == "muscle_gain":
            low, high = kg * 1.6, kg * 2.2
        elif goal == "strength_increase":
            low, high = kg * 1.6, kg * 2.2
        else:
            low, high = kg * 1.2, kg * 1.8
        msg = f"🍗 تناول بين {int(low)} و {int(high)} جرام بروتين يومياً."
        self.responses.append(msg)
        self.declare(AdviceGiven(type='protein'))

    @Rule(WantsSupplementInfo(status=True), NOT(AdviceGiven(type='supplements')))
    def advise_supplements(self):
        self.responses.append("💊 الكرياتين ممتاز للقوة والعضل. 3-5 جم يومياً.")
        self.responses.append("🥤 الواي بروتين: مفيد بعد التمرين.")
        self.declare(AdviceGiven(type='supplements'))

    @Rule(NOT(AdviceGiven(type='hydration')))
    def advise_hydration(self):
        self.responses.append("💧 اشرب ماء كفاية قبل، أثناء وبعد التمرين.")
        self.declare(AdviceGiven(type='hydration'))

    @Rule(ExperienceLevel(level=MATCH.level), NOT(AdviceGiven(type='consistency')))
    def advise_consistency(self, level):
        msg = {
            "beginner": "🔑 كمبتدئ: ركز على بناء عادات صحية.",
            "intermediate": "🔑 كمستخدم متوسط: راقب التقدم وطور التمارين.",
            "advanced": "🔑 كمستخدم متقدم: اهتم بالتخطيط طويل الأمد."
        }.get(level, "استمر في التقدم!")
        self.responses.append(msg)
        self.declare(AdviceGiven(type='consistency'))

def run_expert(goal, level, weight, supplements):
    engine = FitnessExpert()
    engine.reset()
    engine.declare(PrimaryGoal(type=goal))
    engine.declare(ExperienceLevel(level=level))
    engine.declare(BodyWeight(kg=float(weight)))
    engine.declare(WantsSupplementInfo(status=supplements))
    engine.run()
    return "\n".join(engine.responses)

# === Telegram Bot ===

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("💪 عضل", callback_data='muscle_gain')],
        [InlineKeyboardButton("🔥 دهون", callback_data='fat_loss')],
        [InlineKeyboardButton("🏋️ قوة", callback_data='strength_increase')],
        [InlineKeyboardButton("🤸 لياقة", callback_data='general_fitness')],
    ]
    await update.message.reply_text("🎯 اختر هدفك الرياضي:", reply_markup=InlineKeyboardMarkup(keyboard))
    return GOAL

async def goal_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_data["goal"] = update.callback_query.data
    await update.callback_query.answer()
    keyboard = [
        [InlineKeyboardButton("🔰 مبتدئ", callback_data='beginner')],
        [InlineKeyboardButton("⚙️ متوسط", callback_data='intermediate')],
        [InlineKeyboardButton("🧠 متقدم", callback_data='advanced')],
    ]
    await update.callback_query.message.reply_text("📊 اختر مستواك الرياضي:", reply_markup=InlineKeyboardMarkup(keyboard))
    return LEVEL

async def level_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_data["level"] = update.callback_query.data
    await update.callback_query.answer()
    await update.callback_query.message.reply_text("⚖️ أدخل وزنك بالكيلوغرام:")
    return WEIGHT

async def weight_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_data["weight"] = float(update.message.text)
        keyboard = [
            [InlineKeyboardButton("✅ نعم", callback_data='yes')],
            [InlineKeyboardButton("❌ لا", callback_data='no')],
        ]
        await update.message.reply_text("هل ترغب بمعلومات عن المكملات؟", reply_markup=InlineKeyboardMarkup(keyboard))
        return SUPPLEMENTS
    except ValueError:
        await update.message.reply_text("🚫 من فضلك أدخل رقم صحيح للوزن.")
        return WEIGHT

async def supplements_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_data["supplements"] = update.callback_query.data == "yes"
    await update.callback_query.answer()
    msg = run_expert(user_data["goal"], user_data["level"], user_data["weight"], user_data["supplements"])
    await update.callback_query.message.reply_text("📝 نصائحك:\n\n" + msg)
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("تم الإلغاء.")
    return ConversationHandler.END

# ✅ تشغيل البوت
if __name__ == "__main__":
    app = ApplicationBuilder().token(os.environ["TELEGRAM_TOKEN"]).build()
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            GOAL: [CallbackQueryHandler(goal_chosen)],
            LEVEL: [CallbackQueryHandler(level_chosen)],
            WEIGHT: [MessageHandler(filters.TEXT & ~filters.COMMAND, weight_received)],
            SUPPLEMENTS: [CallbackQueryHandler(supplements_chosen)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    app.add_handler(conv_handler)
    app.run_polling()
