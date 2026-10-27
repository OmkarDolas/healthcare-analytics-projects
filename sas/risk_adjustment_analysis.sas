/* Risk Adjustment statistical analysis in SAS (mirrors src/run_analysis.py).
   Works in SAS OnDemand for Academics: upload data/member_years.csv and update the path below. */
%let path = /home/your_user/risk_adjustment;

proc import datafile="&path/member_years.csv" out=member_years dbms=csv replace;
    guessingrows=max;
run;

/* Same exclusions as the SQL data quality checks */
data member_years_clean;
    set member_years;
    if missing(county) or raf_score < 0 or raf_score > 10 then delete;
    female_n = (female = "True");
    dual_n   = (dual_eligible = "True");
run;

/* Average RAF by segment, plan, payment year */
proc sql;
    create table raf_trend as
    select segment, plan, payment_year,
           count(*)        as members,
           mean(raf_score) as avg_raf format=8.4,
           mean(hcc_count) as avg_hcc_count format=8.3
      from member_years_clean
     group by segment, plan, payment_year
     order by segment, plan, payment_year;
quit;
proc print data=raf_trend noobs; run;

/* Welch t-test, 2024 vs 2025 RAF, by segment */
proc sort data=member_years_clean out=t_input;
    by segment;
    where payment_year in (2024, 2025);
run;
proc ttest data=t_input;
    by segment;
    class payment_year;
    var raf_score;
run;

/* Drivers of RAF */
proc glm data=member_years_clean;
    class segment;
    model raf_score = age female_n dual_n hcc_count segment / solution;
run;
quit;

proc sgplot data=raf_trend;
    series x=payment_year y=avg_raf / group=plan markers;
    xaxis values=(2023 2024 2025);
run;
