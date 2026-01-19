Pandas: 
    Pros: Relatively easy to write. I used pandas a lot in data301 so just took a quick refresher on how to use dataframes       and series
   
    Cons: SLOW! I first tried to use read_csv but it tried to read the whole csv in at once which broke the first time. Then had to break it into chunks and read it in that way while being cognizant of data types. Took forever 

Polars: 
    Pros: Pretty fast, not too hard to use after looking up the syntax/docs. It's SQL logic with python syntax pretty much just on dataframes instead of tables. It seems to have a lot of useful functionality once you learn to use it well. 
    
    Cons: Took a bit of time to look up and learn to use properly. It's a little cryptic at first glance just because I haven't used it before

DuckDB: 
    Pros: Runs the fastest of these options. Execution time from 3-6 hours was about the same so it seems to handle increased data size well. 
    Cons: Had to learn it which wasn't fun. I don't enjoy having to write the SQL query verbatim within python as it just doesn't feel streamlined. Had to go back and remember SQL syntax and connect to the DB, just didn't feel like the best way to do it. 