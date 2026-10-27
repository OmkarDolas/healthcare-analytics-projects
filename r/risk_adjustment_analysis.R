# Risk Adjustment statistical analysis in R (mirrors src/run_analysis.py).
# Run from the project root after `python src/generate_data.py`:
#   Rscript r/risk_adjustment_analysis.R
library(dplyr)
library(ggplot2)

my <- read.csv("data/member_years.csv") |>
  mutate(female = as.integer(female == "True"),
         dual_eligible = as.integer(dual_eligible == "True")) |>
  filter(!is.na(county), county != "", raf_score >= 0, raf_score <= 10)   # same exclusions as SQL checks

# Average RAF by plan and year with YoY % change
trend <- my |>
  group_by(segment, plan, payment_year) |>
  summarise(members = n(), avg_raf = mean(raf_score), .groups = "drop") |>
  group_by(segment, plan) |>
  arrange(payment_year, .by_group = TRUE) |>
  mutate(raf_yoy_pct = 100 * (avg_raf / lag(avg_raf) - 1))
print(trend, n = Inf)

# Welch t-test: did RAF change between 2024 and 2025?
for (seg in c("MA", "ACA")) {
  s <- filter(my, segment == seg)
  print(t.test(raf_score ~ payment_year, data = filter(s, payment_year %in% c(2024, 2025))))
}

# Drivers of RAF
model <- lm(raf_score ~ age + female + dual_eligible + hcc_count + segment, data = my)
print(summary(model))

dir.create("outputs/charts", recursive = TRUE, showWarnings = FALSE)
p <- ggplot(trend, aes(payment_year, avg_raf, colour = plan)) +
  geom_line() + geom_point() +
  facet_wrap(~segment, scales = "free_y") +
  labs(title = "Average RAF score by plan", x = "Payment year", y = "Average RAF")
ggsave("outputs/charts/raf_trend_r.png", p, width = 10, height = 4)
