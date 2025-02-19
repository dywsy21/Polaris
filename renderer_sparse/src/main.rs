use rusqlite::{params, Connection};
use plotters::prelude::*;
use plotters::style::FontStyle;
use std::collections::{HashMap, HashSet};
use std::f64::consts::PI;
use std::io::{self, BufRead};
use std::fs::File;
use std::io::BufReader;

fn tile_to_lat_lon(xtile: i32, ytile: i32, zoom: i32) -> (f64, f64) {
    let n = 2.0_f64.powi(zoom);
    let lon = xtile as f64 / n * 360.0 - 180.0;
    let lat_rad = (PI * (1.0 - 2.0 * ytile as f64 / n)).sinh().atan();
    let lat = lat_rad * 180.0 / PI;
    (lat, lon)
}

fn query_nodes_from_db(
    db_path: &str,
    zoom: i32,
    visible_tiles: &[(i32, i32)],
) -> Vec<(f64, f64, HashMap<String, String>)> {
    let conn = Connection::open(db_path).unwrap();
    let mut nodes = Vec::new();

    for &(xtile, ytile) in visible_tiles {
        let (lat_min, lon_min) = tile_to_lat_lon(xtile, ytile + 1, zoom);
        let (lat_max, lon_max) = tile_to_lat_lon(xtile + 1, ytile, zoom);

        let lat_min = lat_min.min(lat_max);
        let lat_max = lat_min.max(lat_max);
        let lon_min = lon_min.min(lon_max);
        let lon_max = lon_min.max(lon_max);

        let approximation_rate = match zoom {
            20 => 0.0000001,
            19 => 0.0000001,
            18 => 0.00000025,
            17 => 0.00000025,
            16 => 0.000001,
            15 => 0.000001,
            14 => 0.000025,
            13 => 0.000025,
            12 => 0.00015,
            11 => 0.00015,
            10 => 0.00045,
            9 => 0.00045,
            8 => 0.00225,
            7 => 0.00225,
            6 => 0.009,
            5 => 0.009,
            4 => 0.036,
            3 => 0.036,
            2 => 0.144,
            1 => 0.144,
            _ => 0.576,
        };

        let sql = "SELECT ROUND(n.lat / ?) * ? AS lat_approx, \
                   ROUND(n.lon / ?) * ? AS lon_approx, \
                   GROUP_CONCAT(t.k || '=' || t.v, ',') AS tags \
                   FROM nodes n \
                   LEFT JOIN tags t ON n.id = t.node_id \
                   WHERE n.lat BETWEEN ? AND ? AND n.lon BETWEEN ? AND ? \
                   GROUP BY lat_approx, lon_approx;";
        let mut stmt = conn.prepare(sql).unwrap();
        let node_iter = stmt
            .query_map(
                params![
                    approximation_rate,
                    approximation_rate,
                    approximation_rate,
                    approximation_rate,
                    lat_min,
                    lat_max,
                    lon_min,
                    lon_max
                ],
                |row| {
                    let lat = row.get(0)?;
                    let lon = row.get(1)?;
                    let tags_text: Option<String> = row.get(2)?;
                    let tags: HashMap<String, String> = tags_text
                        .unwrap_or_default()
                        .split(',')
                        .map(|s| {
                            let mut parts = s.splitn(2, '=');
                            (
                                parts.next().unwrap().to_string(),
                                parts.next().unwrap_or("").to_string(),
                            )
                        })
                        .collect();
                    Ok((lat, lon, tags))
                },
            )
            .unwrap();

        for node in node_iter {
            nodes.push(node.unwrap());
        }
    }

    if nodes.len() > 100 {
        let step = nodes.len() / 50;
        nodes = nodes.into_iter().step_by(step).collect();
    }

    nodes
}

fn get_surrounding_tiles(xtile: i32, ytile: i32) -> Vec<(i32, i32)> {
    let mut tiles = Vec::new();
    for dx in -1..=1 {
        for dy in -1..=1 {
            tiles.push((xtile + dx, ytile + dy));
        }
    }
    tiles
}

fn is_point_in_tile(lat: f64, lon: f64, xtile: i32, ytile: i32, zoom: i32) -> bool {
    let (min_lat, min_lon) = tile_to_lat_lon(xtile, ytile + 1, zoom);
    let (max_lat, max_lon) = tile_to_lat_lon(xtile + 1, ytile, zoom);
    lat >= min_lat && lat <= max_lat && lon >= min_lon && lon <= max_lon
}

fn query_ways_from_db(
    db_path: &str,
    zoom: i32,
    target_tile: (i32, i32),
) -> Vec<(Vec<(f64, f64)>, HashMap<String, String>)> {
    let start = std::time::Instant::now();
    let conn = Connection::open(db_path).unwrap();

    let (tile_min_lat, tile_min_lon) = tile_to_lat_lon(target_tile.0, target_tile.1 + 1, zoom);
    let (tile_max_lat, tile_max_lon) = tile_to_lat_lon(target_tile.0 + 1, target_tile.1, zoom);

    let lat_min = tile_min_lat.min(tile_max_lat);
    let lat_max = tile_min_lat.max(tile_max_lat);
    let lon_min = tile_min_lon.min(tile_max_lon);
    let lon_max = tile_min_lon.max(tile_max_lon);

    // Phase 1: Fetch relevant way IDs based on bounding boxes
    let sql = "SELECT id FROM ways
               WHERE max_lat >= ? AND min_lat <= ? AND
                     max_lon >= ? AND min_lon <= ?";
    let mut stmt = conn.prepare(sql).unwrap();
    let way_ids: Vec<i64> = stmt
        .query_map(params![lat_min, lat_max, lon_min, lon_max], |row| row.get(0))
        .unwrap()
        .filter_map(Result::ok)
        .collect();

    println!("Phase 1: {:?}", start.elapsed());
    let start_phase2 = std::time::Instant::now();

    let approximation_rate = 1;

    // Limit the number of way_ids to process
    let mut way_ids = way_ids;
    if way_ids.len() > 1000 {
        way_ids = way_ids.into_iter().step_by(approximation_rate).collect();
    }

    // Limit for SQLite variables (default is 999)
    let max_sql_vars = 999;

    // Break way_ids into chunks
    let way_id_chunks: Vec<&[i64]> = way_ids.chunks(max_sql_vars / 2).collect();

    // Initialize the maps to collect results
    let mut way_nodes_map: HashMap<i64, Vec<(f64, f64)>> = HashMap::new();
    let mut way_tags_map: HashMap<i64, HashMap<String, String>> = HashMap::new();

    // Fetch nodes and tags for all ways in batches
    for chunk in &way_id_chunks {
        let placeholders = chunk.iter().map(|_| "?").collect::<Vec<_>>().join(",");

        // Fetch nodes for the current batch of way_ids
        let node_query = format!(
            "SELECT wn.way_id, n.lat, n.lon 
             FROM way_nodes wn 
             JOIN nodes n ON wn.node_id = n.id 
             WHERE wn.way_id IN ({}) 
             ORDER BY wn.way_id, wn.rowid",
            placeholders
        );
        let mut node_stmt = conn.prepare(&node_query).unwrap();
        let node_rows = node_stmt
            .query_map(rusqlite::params_from_iter(chunk.iter()), |row| {
                Ok((
                    row.get::<_, i64>(0)?, // way_id
                    row.get::<_, f64>(1)?, // lat
                    row.get::<_, f64>(2)?, // lon
                ))
            })
            .unwrap();

        for node_row in node_rows {
            let (way_id, lat, lon) = node_row.unwrap();
            way_nodes_map
                .entry(way_id)
                .or_insert_with(Vec::new)
                .push((lat, lon));
        }

        // Fetch tags for the current batch of way_ids
        let tag_query = format!(
            "SELECT way_id, k, v FROM way_tags WHERE way_id IN ({})",
            placeholders
        );
        let mut tag_stmt = conn.prepare(&tag_query).unwrap();
        let tag_rows = tag_stmt
            .query_map(rusqlite::params_from_iter(chunk.iter()), |row| {
                Ok((
                    row.get::<_, i64>(0)?,    // way_id
                    row.get::<_, String>(1)?, // key
                    row.get::<_, String>(2)?, // value
                ))
            })
            .unwrap();

        for tag_row in tag_rows {
            let (way_id, key, value) = tag_row.unwrap();
            way_tags_map
                .entry(way_id)
                .or_insert_with(HashMap::new)
                .insert(key, value);
        }
    }

    // Assemble the ways with their nodes and tags
    let mut ways = Vec::new();
    for way_id in way_ids {
        if let Some(nodes_coord) = way_nodes_map.get(&way_id) {
            if !nodes_coord.is_empty() {
                let tags = way_tags_map.get(&way_id).cloned().unwrap_or_default();
                ways.push((nodes_coord.clone(), tags));
            }
        }
    }

    println!("Phase 2: {:?}", start_phase2.elapsed());

    // let elapsed = start.elapsed();
    // println!("Query ways time: {:?}", elapsed);

    ways
}

fn map_to_scene(
    lat: f64,
    lon: f64,
    min_lat: f64,
    max_lat: f64,
    min_lon: f64,
    max_lon: f64,
    scene_width: i32,
    scene_height: i32,
) -> (i32, i32) {
    let x = ((lon - min_lon) / (max_lon - min_lon) * scene_width as f64) as i32;
    let y = ((lat - min_lat) / (max_lat - min_lat) * scene_height as f64) as i32;
    (x, scene_height - y)
}

fn parse_tag_colors(file_path: &str) -> HashMap<String, RGBColor> {
    let file = File::open(file_path).unwrap();
    let reader = BufReader::new(file);
    let mut tag_colors = HashMap::new();

    for line in reader.lines() {
        let line = line.unwrap();
        let parts: Vec<&str> = line.split(':').collect();
        if parts.len() == 2 {
            let tag = parts[0].to_string();
            let color = parts[1].trim_start_matches('#').trim();
            let r = u8::from_str_radix(&color[0..2], 16).unwrap();
            let g = u8::from_str_radix(&color[2..4], 16).unwrap();
            let b = u8::from_str_radix(&color[4..6], 16).unwrap();
            tag_colors.insert(tag, RGBColor(r, g, b));
        }
    }

    tag_colors
}

fn calculate_signed_area(points: &[(i32, i32)]) -> f64 {
    let n = points.len();
    let mut area = 0.0;
    for i in 0..n {
        let (x1, y1) = points[i];
        let (x2, y2) = points[(i + 1) % n];
        area += (x1 as f64 * y2 as f64) - (x2 as f64 * y1 as f64);
    }
    area / 2.0
}

fn cross(o: (i32, i32), a: (i32, i32), b: (i32, i32)) -> i32 {
    (a.0 - o.0) * (b.1 - o.1) - (a.1 - o.1) * (b.0 - o.0)
}

fn convex_hull(mut points: Vec<(i32, i32)>) -> Vec<(i32, i32)> {
    points.sort();
    let mut lower = Vec::new();
    for p in &points {
        while lower.len() >= 2 && cross(lower[lower.len() - 2], lower[lower.len() - 1], *p) <= 0 {
            lower.pop();
        }
        lower.push(*p);
    }

    let mut upper = Vec::new();
    for p in points.iter().rev() {
        while upper.len() >= 2 && cross(upper[upper.len() - 2], upper[upper.len() - 1], *p) <= 0 {
            upper.pop();
        }
        upper.push(*p);
    }

    lower.pop();
    upper.pop();
    lower.append(&mut upper);
    lower
}

fn render_map(zoom: i32, xtile: i32, ytile: i32) {
    let cache_dir = format!("./cache_renderer_sparse/{}/", zoom);
    std::fs::create_dir_all(&cache_dir).unwrap();
    let cache_file_path = format!("{}{}_{}.png", cache_dir, xtile, ytile);

    if std::path::Path::new(&cache_file_path).exists() {
        println!("Tile already cached: {}", cache_file_path);
        return;
    }

    let start = std::time::Instant::now();
    let (min_lat, min_lon) = tile_to_lat_lon(xtile, ytile + 1, zoom);
    let (max_lat, max_lon) = tile_to_lat_lon(xtile + 1, ytile, zoom);

    let scene_width = 800;
    let scene_height = 600;

    let db_path = "map_data/map.db";
    let ways = query_ways_from_db(db_path, zoom, (xtile, ytile));

    // Filter ways based on 'highway' tag and zoom level
    let filtered_ways: Vec<(Vec<(f64, f64)>, HashMap<String, String>)> = ways
        .into_iter()
        .filter(|(_, tags)| {
            if zoom > 13 {
                true // No filtering for zoom levels above 13
            } else if let Some(highway_value) = tags.get("highway") {
                match zoom {
                    11..=13 => ["motorway", "trunk", "primary", "secondary", "tertiary"].contains(&highway_value.as_str()),
                    8..=10 => ["motorway", "trunk", "primary", "secondary"].contains(&highway_value.as_str()),
                    5..=7 => ["motorway", "trunk", "primary"].contains(&highway_value.as_str()),
                    _ if zoom < 6 => highway_value == "motorway" || highway_value == "trunk",
                    _ => false,
                }
            } else {
                false // Exclude ways without 'highway' tag
            }
        })
        .collect();

    let start2 = std::time::Instant::now();

    let root = BitMapBackend::new(&cache_file_path, (scene_width as u32, scene_height as u32)).into_drawing_area();
    let background_color = RGBColor(242, 239, 233); // #f2efe9
    root.fill(&background_color).unwrap();

    let tag_colors = parse_tag_colors("tags.txt");

    let enclosed_tags = vec![
        "building",
        "park",
        "garden",
        "leisure",
        "landuse",
        "natural",
        "historic",
    ];

    let font = ("SimHei", 16).into_font();

    let mut name_tags = Vec::new();
    let mut rendered_names = HashSet::new();

    for (nodes_coord, tags) in filtered_ways {
        let mut points = Vec::new();
        for (lat, lon) in &nodes_coord {
            let (x, y) = map_to_scene(*lat, *lon, min_lat, max_lat, min_lon, max_lon, scene_width, scene_height);
            points.push((x as i32, y as i32));
        }

        if points.len() >= 2 {
            let mut color = RGBColor(173, 216, 230); // Default color

            for (tag, tag_color) in &tag_colors {
                if tags.contains_key(tag) {
                    color = *tag_color;
                    break;
                }
            }

            let has_enclosed_tag = tags.keys().any(|tag| enclosed_tags.contains(&tag.as_str()));

            if has_enclosed_tag {
                points = convex_hull(points);
                root.draw(&Polygon::new(points.clone(), ShapeStyle::from(&color).filled())).unwrap();
            } else {
                root.draw(&PathElement::new(points.clone(), ShapeStyle::from(&color).stroke_width(2))).unwrap();
            }

            if let Some(name) = tags.get("name") {
                if zoom >= 15 && !rendered_names.contains(name) {
                    let (x, y) = points[points.len() / 2];
                    name_tags.push((name.clone(), (x, y)));
                    rendered_names.insert(name.clone());
                }
            }
        }
    }

    // Draw name tags on top
    for (name, (x, y)) in name_tags {
        let text_width = name.len() as i32 * 8; // Approximate text width
        let text_height = 16; // Approximate text height

        // Ensure the text does not exceed the border
        let x = x.min(scene_width - text_width).max(0);
        let y = y.min(scene_height - text_height).max(text_height);

        root.draw(&Text::new(name, (x, y), font.clone())).unwrap();
    }

    // Ensure the drawing is saved before copying
    root.present().unwrap();

    // Copy the rendered tile to ./rendered_tile.png
    if let Err(e) = std::fs::copy(&cache_file_path, "rendered_tile.png") {
        println!("Failed to copy rendered tile: {}", e);
    }

    let elapsed = start2.elapsed();
    println!("Render map time: {:?}", elapsed);
}

fn main() {
    let stdin = io::stdin();
    let mut lines = stdin.lock().lines();
    if let Some(Ok(line)) = lines.next() {
        let parts: Vec<i32> = line.split_whitespace().map(|s| s.parse().unwrap()).collect();
        if parts.len() == 3 {
            // time the rendering process
            let start = std::time::Instant::now();
            render_map(parts[0], parts[1], parts[2]);
            let elapsed = start.elapsed();
            println!("Total time: {:?}", elapsed);
        }
    }
}
