<?php
header("Content-Type: application/json");
header("Access-Control-Allow-Origin: *");
header("Access-Control-Allow-Methods: GET, POST");

ini_set('memory_limit', '256M');
ini_set('max_execution_time', 60);

error_log("API version: 2025-07-16-timbang-fix-cashier-sync");

function return_json($data) {
    echo json_encode($data);
    exit;
}

// Database connection
$host = "localhost";
$username = "root";
$password = "";
$database = "mypos";

$conn = new mysqli($host, $username, $password, $database);
if ($conn->connect_error) {
    error_log("Database connection failed: " . $conn->connect_error);
    return_json(["status" => "error", "message" => "Connection failed: " . $conn->connect_error]);
}

// Parse POST data
$data = [];
if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    $raw_input = file_get_contents("php://input");
    error_log("Raw POST input: " . $raw_input);
    $data = json_decode($raw_input, true);
    if (json_last_error() !== JSON_ERROR_NONE) {
        return_json(["status" => "error", "message" => "Invalid JSON format: " . json_last_error_msg()]);
    }
}

// LOGIN USER
if ($_SERVER['REQUEST_METHOD'] === 'POST' && isset($data['action']) && $data['action'] == 'login') {
    if (!isset($data['username']) || !isset($data['password'])) {
        return_json(["status" => "error", "message" => "Username and password required"]);
    }
    $username = trim($data['username']);
    $password = $data['password'];
    $sql = "SELECT id, username, password, role FROM users WHERE username = ?";
    $stmt = $conn->prepare($sql);
    $stmt->bind_param("s", $username);
    $stmt->execute();
    $result = $stmt->get_result();
    if ($result->num_rows > 0) {
        $user = $result->fetch_assoc();
        if (password_verify($password, $user['password'])) {
            return_json([
                "status" => "success",
                "user" => [
                    "id" => $user['id'],
                    "username" => $user['username'],
                    "role" => $user['role'] ?? "user"
                ],
                "message" => "Login successful"
            ]);
        } else {
            return_json(["status" => "error", "message" => "Invalid credentials"]);
        }
    } else {
        return_json(["status" => "error", "message" => "User not found"]);
    }
    $stmt->close();
}

// GET LOW STOCK PRODUCTS
elseif ($_SERVER['REQUEST_METHOD'] === 'GET' && isset($_GET['action']) && $_GET['action'] == 'get_low_stock_products') {
    $threshold = 5;
    $sql = "SELECT 
                i.id,
                i.item_name as name,
                (SELECT sp.supplier_price_unit 
                 FROM supplier_prices sp 
                 WHERE sp.item_id = i.id 
                 ORDER BY sp.date_keyin DESC 
                 LIMIT 1) as price,
                i.barcode_per_unit as barcode,
                (COALESCE(SUM(sp.stock_per_unit), 0) - 
                COALESCE((SELECT SUM(si.quantity) 
                         FROM sales_items si
                         JOIN sales s ON si.sale_id = s.id
                         WHERE si.item_id = i.id), 0)) as stock
            FROM items i
            LEFT JOIN supplier_prices sp ON i.id = sp.item_id
            GROUP BY i.id
            HAVING stock <= ?
            ORDER BY stock ASC";
    $stmt = $conn->prepare($sql);
    if (!$stmt) {
        return_json(['status' => 'error', 'message' => 'Prepare failed: ' . $conn->error]);
    }
    $stmt->bind_param("i", $threshold);
    $stmt->execute();
    $result = $stmt->get_result();
    $products = [];
    while ($row = $result->fetch_assoc()) {
        $products[] = [
            'id' => $row['id'],
            'name' => $row['name'],
            'price' => $row['price'],
            'barcode' => $row['barcode'],
            'stock' => (int)$row['stock'],
            'status' => ($row['stock'] <= 0) ? 'HABIS' : 'KRITIKAL'
        ];
    }
    return_json(['status' => 'success', 'products' => $products]);
    $stmt->close();
}

// GET PRODUCT BY BARCODE
elseif ($_SERVER['REQUEST_METHOD'] === 'GET' && !isset($_GET['action']) && isset($_GET['barcode'])) {
    $barcode = trim($_GET['barcode']);
    $debug = "Scanning barcode: $barcode\n";
    $checkSql = "SELECT i.id, i.item_name, i.barcode_per_unit, i.barcode_per_pack, i.barcode_per_box,
                        COALESCE(sp.stock_per_unit, 0) as stock
                 FROM items i
                 LEFT JOIN supplier_prices sp ON sp.item_id = i.id
                 WHERE ? IN (i.barcode_per_unit, i.barcode_per_pack, i.barcode_per_box)
                 ORDER BY sp.date_keyin DESC LIMIT 1";
    $checkStmt = $conn->prepare($checkSql);
    if (!$checkStmt) {
        $debug .= "Check prepare failed: " . $conn->error . "\n";
        return_json(['status' => 'error', 'message' => 'Check prepare failed', 'debug' => $debug]);
    }
    $checkStmt->bind_param("s", $barcode);
    $checkStmt->execute();
    $checkResult = $checkStmt->get_result();
    $itemCheck = $checkResult->fetch_assoc();
    $debug .= "Items check result: " . print_r($itemCheck, true) . "\n";
    $checkStmt->close();
    if (!$itemCheck) {
        return_json(['status' => 'error', 'message' => 'Produk tidak wujud', 'debug' => $debug]);
    }
    if ($itemCheck['stock'] <= 0) {
        return_json(['status' => 'error', 'message' => 'Stok habis', 'debug' => $debug]);
    }
    $sql = "SELECT 
                i.id, 
                i.item_name as name,
                COALESCE(
                    (SELECT sp.supplier_price_box 
                     FROM supplier_prices sp 
                     WHERE sp.item_id = i.id 
                     AND sp.pack_per_box > 0 
                     AND ? = i.barcode_per_box 
                     ORDER BY sp.date_keyin DESC LIMIT 1),
                    (SELECT sp.supplier_price_pack 
                     FROM supplier_prices sp 
                     WHERE sp.item_id = i.id 
                     AND sp.unit_per_pack > 0 
                     AND ? = i.barcode_per_pack 
                     ORDER BY sp.date_keyin DESC LIMIT 1),
                    (SELECT sp.supplier_price_unit 
                     FROM supplier_prices sp 
                     WHERE sp.item_id = i.id 
                     AND ? = i.barcode_per_unit 
                     ORDER BY sp.date_keyin DESC LIMIT 1)
                ) as price,
                i.barcode_per_unit,
                i.barcode_per_pack,
                i.barcode_per_box,
                i.is_weighable,
                i.unit_of_measurement
            FROM items i
            WHERE ? IN (i.barcode_per_unit, i.barcode_per_pack, i.barcode_per_box)
            LIMIT 1";
    $stmt = $conn->prepare($sql);
    if (!$stmt) {
        $debug .= "Prepare failed: " . $conn->error . "\n";
        return_json(['status' => 'error', 'message' => 'Prepare failed: ' . $conn->error, 'debug' => $debug]);
    }
    $stmt->bind_param("ssss", $barcode, $barcode, $barcode, $barcode);
    $stmt->execute();
    $result = $stmt->get_result();
    $product = $result->fetch_assoc();
    if ($product) {
        $matched_barcode_type = '';
        if (trim($product['barcode_per_unit']) === trim($barcode)) {
            $matched_barcode_type = 'unit';
        } elseif (trim($product['barcode_per_pack']) === trim($barcode)) {
            $matched_barcode_type = 'pack';
        } elseif (trim($product['barcode_per_box']) === trim($barcode)) {
            $matched_barcode_type = 'box';
        }
        $debug .= "Found product: " . print_r($product, true) . "\n";
        return_json([
            'status' => 'success',
            'data' => [
                'id' => $product['id'],
                'name' => $product['name'],
                'price' => $product['price'] ?? 0.00,
                'barcode' => $barcode,
                'barcode_type' => $matched_barcode_type,
                'is_weighable' => isset($product['is_weighable']) ? (int)$product['is_weighable'] : 0,
                'unit_of_measurement' => $product['unit_of_measurement'] ?? ''
            ],
            'debug' => $debug
        ]);
    } else {
        $debug .= "Product not found for barcode: $barcode. Query result: " . print_r($result->fetch_all(), true) . "\n";
        return_json(["status" => "error", "message" => "Product not found", 'debug' => $debug]);
    }
    $stmt->close();
}

// SAVE TRANSACTION
elseif ($_SERVER['REQUEST_METHOD'] === 'POST' && isset($data['action']) && $data['action'] == 'save_transaction') {
    $conn->begin_transaction();
    try {
        $required_fields = ['sale_id', 'user_id', 'items', 'total', 'discount', 'amount_paid', 'payment_method_id', 'payment_method', 'cashier_id'];
        foreach ($required_fields as $field) {
            if (!isset($data[$field]) || ($field == 'cashier_id' && empty($data[$field]))) {
                throw new Exception("Missing or empty required field: $field");
            }
        }
        $sale_id = $conn->real_escape_string($data['sale_id']);
        $receipt_no = "INV" . date("Ymd") . str_pad(mt_rand(1, 9999), 4, '0', STR_PAD_LEFT);
        $payment_method_id = (int)$data['payment_method_id'];
        $payment_method_text = $conn->real_escape_string($data['payment_method']);
        $user_id = (int)$data['user_id'];
        $cashier_id = $conn->real_escape_string($data['cashier_id']);
        $total = (float)$data['total'];
        $discount = (float)$data['discount'];
        $amount_paid = (float)$data['amount_paid'];
        $change = $amount_paid - $total;
        $created_at = date('Y-m-d H:i:s');

        $stmt = $conn->prepare("INSERT INTO sales (id, receipt_no, sale_date, user_id, total, discount, payment_received, change_given, payment_method_id, cashier_id, created_at, synced) VALUES (?, ?, NOW(), ?, ?, ?, ?, ?, ?, ?, ?, 0)");
        $stmt->bind_param("ssiddddiss", $sale_id, $receipt_no, $user_id, $total, $discount, $amount_paid, $change, $payment_method_id, $cashier_id, $created_at);
        $stmt->execute();
        $stmt->close();

        foreach ($data['items'] as $item) {
            $item_name = $conn->real_escape_string($item['name']);
            $quantity = (float)$item['quantity'];
            $unit_price = round((float)$item['price'], 4);
            $total_price = round((float)$item['total'], 4);

            $stmt = $conn->prepare("SELECT i.id FROM items i WHERE i.item_name = ? LIMIT 1");
            $stmt->bind_param("s", $item_name);
            $stmt->execute();
            $result = $stmt->get_result();
            $item_data = $result->fetch_assoc();
            $item_id = $item_data ? (int)$item_data['id'] : null;
            $stmt->close();

            if ($item_id) {
                $item_sale_id = $conn->real_escape_string($sale_id . "-" . $item_id);
                $stmt = $conn->prepare("INSERT INTO sales_items (id, sale_id, item_id, quantity, unit_price, total_price, cashier_id, created_at, synced) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0)");
                $stmt->bind_param("ssiddsss", $item_sale_id, $sale_id, $item_id, $quantity, $unit_price, $total_price, $cashier_id, $created_at);
                $stmt->execute();
                $stmt->close();

                $updateStockSql = "UPDATE supplier_prices 
                                  SET stock_per_unit = stock_per_unit - ?, 
                                      synced = 0, 
                                      updated_at = NOW() 
                                  WHERE item_id = ? 
                                  ORDER BY date_keyin DESC 
                                  LIMIT 1";
                $updateStockStmt = $conn->prepare($updateStockSql);
                $updateStockStmt->bind_param("di", $quantity, $item_id);
                $updateStockStmt->execute();
                $updateStockStmt->close();
            } else {
                throw new Exception("Item not found: $item_name");
            }
        }

        if ($payment_method_id == 2 && isset($data['customer_info'])) {
            $customer_info = $data['customer_info'];
            $customer_name = $conn->real_escape_string($customer_info['name'] ?? '');
            $phone = $conn->real_escape_string($customer_info['phone'] ?? '');
            $address = $conn->real_escape_string($customer_info['address'] ?? '');
            $stmt = $conn->prepare("INSERT INTO customer_credit (sale_id, customer_name, phone, address, amount, due_date, synced) VALUES (?, ?, ?, ?, ?, DATE_ADD(NOW(), INTERVAL 30 DAY), 0)");
            $stmt->bind_param("isssd", $sale_id, $customer_name, $phone, $address, $total);
            $stmt->execute();
            $stmt->close();
        }

        if ($payment_method_id == 1) {
            $shift_query = "SELECT id, cash_end FROM shifts WHERE user_id = ? AND cashier_id = ? AND shift_end IS NULL ORDER BY shift_start DESC LIMIT 1";
            $shift_stmt = $conn->prepare($shift_query);
            $shift_stmt->bind_param("is", $user_id, $cashier_id);
            $shift_stmt->execute();
            $shift_result = $shift_stmt->get_result();
            if ($shift_result->num_rows > 0) {
                $shift = $shift_result->fetch_assoc();
                $new_cash_end = $shift['cash_end'] + $total;
                $update_query = "UPDATE shifts SET cash_end = ?, synced = 0, updated_at = NOW() WHERE id = ?";
                $update_stmt = $conn->prepare($update_query);
                $update_stmt->bind_param("di", $new_cash_end, $shift['id']);
                $update_stmt->execute();
                $update_stmt->close();
            } else {
                // Buat syif baru jika tiada syif aktif
                $cash_start = 0.00; // Nilai lalai atau dari konfigurasi
                $shift_insert_query = "INSERT INTO shifts (user_id, cashier_id, shift_start, cash_start, cash_end, synced, updated_at) 
                                     VALUES (?, ?, NOW(), ?, ?, 0, NOW())";
                $shift_insert_stmt = $conn->prepare($shift_insert_query);
                $shift_insert_stmt->bind_param("isdd", $user_id, $cashier_id, $cash_start, $total);
                $shift_insert_stmt->execute();
                $shift_insert_stmt->close();
            }
            $shift_stmt->close();
        }

        $conn->commit();
        return_json([
            'status' => 'success',
            'message' => 'Transaction saved successfully',
            'data' => [
                'receipt_no' => $receipt_no,
                'sale_id' => $sale_id,
                'payment_method' => $payment_method_text,
                'total' => $total,
                'discount' => $discount,
                'amount_paid' => $amount_paid,
                'change_given' => $change
            ]
        ]);
    } catch (Exception $e) {
        $conn->rollback();
        return_json([
            'status' => 'error',
            'message' => 'Transaction failed: ' . $e->getMessage()
        ]);
        error_log("Transaction failed: " . $e->getMessage());
    }
}

// SEARCH PRODUCTS
elseif ($_SERVER['REQUEST_METHOD'] === 'GET' && (isset($_GET['search']) || (isset($_GET['action']) && $_GET['action'] == 'search_products'))) {
    $search_term = isset($_GET['search']) ? $_GET['search'] : (isset($_GET['query']) ? $_GET['query'] : '');
    $search = "%" . $conn->real_escape_string(strtolower($search_term)) . "%";
    $limit = isset($_GET['limit']) ? (int)$_GET['limit'] : 10;

    $sql = "
        SELECT 
            i.id,
            i.item_name as name,
            MAX(sp.supplier_price_unit) as price_unit,
            MAX(sp.supplier_price_pack) as price_pack,
            MAX(sp.supplier_price_box) as price_box,
            i.barcode_per_unit,
            i.barcode_per_pack,
            i.barcode_per_box,
            (COALESCE(SUM(sp.stock_per_unit), 0) - 
             COALESCE((SELECT SUM(si.quantity) 
                      FROM sales_items si
                      JOIN sales s ON si.sale_id = s.id
                      WHERE si.item_id = i.id), 0)) as stock,
            MAX(i.is_weighable) as is_weighable,
            MAX(i.unit_of_measurement) as unit_of_measurement,
            MAX(sp.unit_per_pack) as unit_per_pack,
            MAX(sp.pack_per_box) as pack_per_box
        FROM items i
        LEFT JOIN (
            SELECT item_id, MAX(date_keyin) as max_date
            FROM supplier_prices
            GROUP BY item_id
        ) latest_date ON i.id = latest_date.item_id
        LEFT JOIN supplier_prices sp ON 
            sp.item_id = latest_date.item_id AND 
            sp.date_keyin = latest_date.max_date
        WHERE LOWER(i.item_name) LIKE ?
        GROUP BY i.id, i.item_name, i.barcode_per_unit, i.barcode_per_pack, i.barcode_per_box
        ORDER BY 
            CASE 
                WHEN LOWER(i.item_name) LIKE ? THEN 0
                WHEN LOWER(i.item_name) LIKE ? THEN 1
                ELSE 2
            END,
            i.item_name
        LIMIT ?";
    $stmt = $conn->prepare($sql);
    if (!$stmt) {
        return_json(['status' => 'error', 'message' => 'Prepare failed: ' . $conn->error]);
    }
    $exact_match = $conn->real_escape_string(strtolower($search_term)) . "%";
    $starts_with = $conn->real_escape_string(strtolower($search_term)) . "%";
    $stmt->bind_param("sssi", $search, $exact_match, $starts_with, $limit);
    $stmt->execute();
    $result = $stmt->get_result();
    $products = [];
    while ($row = $result->fetch_assoc()) {
        $unit_price = (float)$row['price_unit'];
        $unit_per_pack = max((int)$row['unit_per_pack'], 1);
        $pack_per_box = max((int)$row['pack_per_box'], 1);
        $total_stock = (int)$row['stock'];
        if (!empty($row['barcode_per_unit'])) {
            $products[] = [
                'id' => (int)$row['id'],
                'name' => $row['name'],
                'price' => round($unit_price, 2),
                'barcode' => $row['barcode_per_unit'],
                'stock' => $total_stock,
                'is_weighable' => (int)$row['is_weighable'],
                'unit_of_measurement' => $row['unit_of_measurement'] ?? '',
                'barcode_type' => 'unit'
            ];
        }
        if (!empty($row['barcode_per_pack'])) {
            $pack_price = ($row['price_pack'] > 0) ? (float)$row['price_pack'] : round($unit_price * $unit_per_pack, 2);
            $pack_stock = ($unit_per_pack > 0) ? (int)($total_stock / $unit_per_pack) : 0;
            $products[] = [
                'id' => (int)$row['id'],
                'name' => $row['name'] . ' (Pek)',
                'price' => $pack_price,
                'barcode' => $row['barcode_per_pack'],
                'stock' => $pack_stock,
                'is_weighable' => (int)$row['is_weighable'],
                'unit_of_measurement' => $row['unit_of_measurement'] ?? '',
                'barcode_type' => 'pack'
            ];
        }
        if (!empty($row['barcode_per_box'])) {
            $box_price = ($row['price_box'] > 0) ? (float)$row['price_box'] : round($unit_price * $unit_per_pack * $pack_per_box, 2);
            $box_stock = ($unit_per_pack > 0 && $pack_per_box > 0) ? (int)($total_stock / ($unit_per_pack * $pack_per_box)) : 0;
            $products[] = [
                'id' => (int)$row['id'],
                'name' => $row['name'] . ' (Kotak)',
                'price' => $box_price,
                'barcode' => $row['barcode_per_box'],
                'stock' => $box_stock,
                'is_weighable' => (int)$row['is_weighable'],
                'unit_of_measurement' => $row['unit_of_measurement'] ?? '',
                'barcode_type' => 'box'
            ];
        }
    }
    return_json([
        'status' => 'success',
        'data' => $products,
        'count' => count($products)
    ]);
    $stmt->close();
}

// CHECK SHIFT
elseif ($_SERVER['REQUEST_METHOD'] === 'GET' && isset($_GET['action']) && $_GET['action'] == 'check_shift' && isset($_GET['user_id']) && isset($_GET['cashier_id'])) {
    $user_id = (int)$_GET['user_id'];
    $cashier_id = $conn->real_escape_string($_GET['cashier_id']);
    $sql = "SELECT s.id, s.cash_start, s.cash_end, s.shift_start, u.username AS cashier_name
            FROM shifts s
            LEFT JOIN users u ON s.user_id = u.id
            WHERE s.user_id = ? AND s.cashier_id = ? AND s.shift_end IS NULL
            ORDER BY s.shift_start DESC LIMIT 1";
    $stmt = $conn->prepare($sql);
    $stmt->bind_param("is", $user_id, $cashier_id);
    $stmt->execute();
    $result = $stmt->get_result();
    if ($row = $result->fetch_assoc()) {
        return_json([
            'status' => 'success',
            'has_shift' => true,
            'shift_data' => [
                'shift_id' => $row['id'],
                'cashier_name' => $row['cashier_name'],
                'shift_start' => $row['shift_start'],
                'cash_start' => (float)$row['cash_start'],
                'cash_end' => (float)$row['cash_end']
            ]
        ]);
    } else {
        return_json([
            'status' => 'success',
            'has_shift' => false,
            'message' => 'Tiada syif aktif untuk cashier_id: ' . $cashier_id
        ]);
    }
    $stmt->close();
}

// START SHIFT
elseif ($_SERVER['REQUEST_METHOD'] === 'POST' && isset($data['action']) && $data['action'] == 'start_shift') {
    if (!isset($data['user_id']) || !isset($data['cash_start']) || !isset($data['cashier_id']) || empty($data['cashier_id'])) {
        return_json(['status' => 'error', 'message' => 'user_id, cash_start, dan cashier_id diperlukan']);
    }
    $user_id = (int)$data['user_id'];
    $cash_start = (float)$data['cash_start'];
    $cashier_id = $conn->real_escape_string($data['cashier_id']);
    $now = date('Y-m-d H:i:s');

    // Pastikan tiada syif aktif untuk cashier_id ini
    $sql = "SELECT id FROM shifts WHERE user_id = ? AND cashier_id = ? AND shift_end IS NULL";
    $stmt = $conn->prepare($sql);
    $stmt->bind_param("is", $user_id, $cashier_id);
    $stmt->execute();
    $result = $stmt->get_result();
    if ($result->num_rows > 0) {
        return_json(['status' => 'error', 'message' => 'Syif sudah bermula untuk cashier_id: ' . $cashier_id]);
    }
    $stmt->close();

    // Insert syif baru
    $sql = "INSERT INTO shifts (user_id, cashier_id, shift_start, cash_start, cash_end, synced, updated_at) 
            VALUES (?, ?, ?, ?, ?, 0, NOW())";
    $stmt = $conn->prepare($sql);
    $stmt->bind_param("issdd", $user_id, $cashier_id, $now, $cash_start, $cash_start);
    if ($stmt->execute()) {
        return_json(['status' => 'success', 'message' => 'Syif bermula untuk cashier_id: ' . $cashier_id]);
    } else {
        return_json(['status' => 'error', 'message' => 'Gagal mula syif: ' . $stmt->error]);
    }
    $stmt->close();
}

// CLOSE SHIFT
elseif ($_SERVER['REQUEST_METHOD'] === 'POST' && isset($data['action']) && $data['action'] == 'close_shift') {
    if (!isset($data['user_id']) || !isset($data['cash_end']) || !isset($data['cashier_id']) || empty($data['cashier_id'])) {
        return_json(['status' => 'error', 'message' => 'user_id, cash_end, dan cashier_id diperlukan']);
    }
    $user_id = (int)$data['user_id'];
    $cash_end = (float)$data['cash_end'];
    $cashier_id = $conn->real_escape_string($data['cashier_id']);

    // Cari syif aktif
    $sql = "SELECT id, cash_start, cash_end FROM shifts WHERE user_id = ? AND cashier_id = ? AND shift_end IS NULL ORDER BY shift_start DESC LIMIT 1";
    $stmt = $conn->prepare($sql);
    $stmt->bind_param("is", $user_id, $cashier_id);
    $stmt->execute();
    $result = $stmt->get_result();
    if ($shift = $result->fetch_assoc()) {
        $shift_id = $shift['id'];
        $cash_start = (float)$shift['cash_start'];
        $expected_cash = (float)$shift['cash_end'];
        $difference = $cash_end - $expected_cash;
        $now = date('Y-m-d H:i:s');
        $sql_update = "UPDATE shifts SET shift_end = ?, cash_end = ?, expected_cash = ?, cash_difference = ?, synced = 0, updated_at = NOW() WHERE id = ?";
        $stmt2 = $conn->prepare($sql_update);
        $stmt2->bind_param("sdddi", $now, $cash_end, $expected_cash, $difference, $shift_id);
        if ($stmt2->execute()) {
            return_json(['status' => 'success', 'message' => 'Syif ditutup untuk cashier_id: ' . $cashier_id]);
        } else {
            return_json(['status' => 'error', 'message' => 'Gagal menutup syif: ' . $stmt2->error]);
        }
        $stmt2->close();
    } else {
        return_json(['status' => 'error', 'message' => 'Tiada syif aktif untuk cashier_id: ' . $cashier_id]);
    }
    $stmt->close();
}

// GET TODAY'S SALES
elseif ($_SERVER['REQUEST_METHOD'] === 'GET' && isset($_GET['action']) && $_GET['action'] == 'get_today_sales' && isset($_GET['date'])) {
    $date = $_GET['date'];
    error_log("Get today's sales: date=$date");
    if (!DateTime::createFromFormat('Y-m-d', $date)) {
        return_json(['status' => 'error', 'message' => 'Invalid date format. Please use YYYY-MM-DD format']);
    }
    $sql = "SELECT 
                @row_number:=@row_number+1 AS no,
                s.receipt_no,
                DATE_FORMAT(s.sale_date, '%Y-%m-%d %H:%i:%s') as sale_time,
                s.total,
                s.discount,
                s.payment_received as amount_paid,
                s.change_given,
                pm.method_name as payment_method,
                CASE 
                    WHEN cc.id IS NULL THEN 'Lunas' 
                    ELSE 'Hutang' 
                END as status
            FROM sales s
            LEFT JOIN payment_methods pm ON s.payment_method_id = pm.id
            LEFT JOIN customer_credit cc ON s.id = cc.sale_id,
            (SELECT @row_number:=0) AS t
            WHERE s.sale_date >= ? AND s.sale_date < DATE_ADD(?, INTERVAL 1 DAY)
            ORDER BY s.sale_date DESC";
    $stmt = $conn->prepare($sql);
    if (!$stmt) {
        return_json(['status' => 'error', 'message' => 'Prepare failed: ' . $conn->error]);
    }
    $stmt->bind_param("ss", $date, $date);
    $stmt->execute();
    $result = $stmt->get_result();
    $sales = [];
    while ($row = $result->fetch_assoc()) {
        $sales[] = [
            'no' => $row['no'],
            'receipt_no' => $row['receipt_no'],
            'sale_time' => $row['sale_time'],
            'total' => number_format($row['total'], 2),
            'discount' => number_format($row['discount'], 2),
            'amount_paid' => number_format($row['amount_paid'], 2),
            'change_given' => number_format($row['change_given'], 2),
            'payment_method' => $row['payment_method'],
            'status' => $row['status']
        ];
    }
    return_json([
        'status' => 'success',
        'data' => $sales
    ]);
    $stmt->close();
}

// CHECK STOCK
elseif ($_SERVER['REQUEST_METHOD'] === 'GET' && isset($_GET['action']) && $_GET['action'] == 'check_stock') {
    $product_name = $_GET['product'];
    $sql = "SELECT id FROM items WHERE item_name = ?";
    $stmt = $conn->prepare($sql);
    if (!$stmt) {
        return_json(['status' => 'error', 'message' => 'Prepare failed: ' . $conn->error]);
    }
    $stmt->bind_param("s", $product_name);
    $stmt->execute();
    $result = $stmt->get_result();
    if ($result->num_rows > 0) {
        $item = $result->fetch_assoc();
        $item_id = $item['id'];
        $sql_stock = "SELECT COALESCE(SUM(stock_per_unit), 0) as total_stock 
                      FROM supplier_prices 
                      WHERE item_id = ?";
        $stmt_stock = $conn->prepare($sql_stock);
        if (!$stmt_stock) {
            return_json(['status' => 'error', 'message' => 'Prepare failed: ' . $conn->error]);
        }
        $stmt_stock->bind_param("i", $item_id);
        $stmt_stock->execute();
        $result_stock = $stmt_stock->get_result();
        $stock_data = $result_stock->fetch_assoc();
        $total_stock = $stock_data['total_stock'];
        $sql_sold = "SELECT COALESCE(SUM(quantity), 0) as total_sold 
                     FROM sales_items 
                     WHERE item_id = ?";
        $stmt_sold = $conn->prepare($sql_sold);
        if (!$stmt_sold) {
            return_json(['status' => 'error', 'message' => 'Prepare failed: ' . $conn->error]);
        }
        $stmt_sold->bind_param("i", $item_id);
        $stmt_sold->execute();
        $result_sold = $stmt_sold->get_result();
        $sold_data = $result_sold->fetch_assoc();
        $total_sold = $sold_data['total_sold'];
        $current_stock = $total_stock - $total_sold;
        return_json([
            'status' => 'success',
            'stock' => (int)$current_stock
        ]);
        $stmt_stock->close();
        $stmt_sold->close();
    } else {
        return_json([
            'status' => 'error',
            'message' => 'Product not found'
        ]);
    }
    $stmt->close();
}

// GET TRANSACTION DETAILS
elseif ($_SERVER['REQUEST_METHOD'] === 'GET' && isset($_GET['action']) && $_GET['action'] == 'get_transaction' && isset($_GET['receipt_no'])) {
    $receipt_no = $_GET['receipt_no'];
    $sql = "SELECT 
                s.id,
                s.receipt_no,
                DATE_FORMAT(s.sale_date, '%Y-%m-%d %H:%i:%s') as sale_date,
                s.total,
                s.discount,
                s.payment_received as amount_paid,
                s.change_given,
                pm.method_name as payment_method,
                cc.customer_name,
                cc.phone,
                cc.address
            FROM sales s
            LEFT JOIN payment_methods pm ON s.payment_method_id = pm.id
            LEFT JOIN customer_credit cc ON s.id = cc.sale_id
            WHERE s.receipt_no = ?";
    $stmt = $conn->prepare($sql);
    if (!$stmt) {
        return_json(['status' => 'error', 'message' => 'Prepare failed: ' . $conn->error]);
    }
    $stmt->bind_param("s", $receipt_no);
    $stmt->execute();
    $result = $stmt->get_result();
    if ($result->num_rows > 0) {
        $transaction = $result->fetch_assoc();
        $sale_id = $transaction['id'];
        $sql_items = "SELECT 
                        i.item_name as name,
                        si.quantity,
                        si.unit_price as price,
                        si.total_price as total
                      FROM sales_items si
                      JOIN items i ON si.item_id = i.id
                      WHERE si.sale_id = ?";
        $stmt_items = $conn->prepare($sql_items);
        if (!$stmt_items) {
            return_json(['status' => 'error', 'message' => 'Prepare failed: ' . $conn->error]);
        }
        $stmt_items->bind_param("s", $sale_id);
        $stmt_items->execute();
        $result_items = $stmt_items->get_result();
        $items = [];
        while ($item = $result_items->fetch_assoc()) {
            $items[] = [
                'name' => $item['name'],
                'quantity' => $item['quantity'],
                'price' => $item['price'],
                'total' => $item['total']
            ];
        }
        $customer_info = null;
        if ($transaction['customer_name']) {
            $customer_info = [
                'name' => $transaction['customer_name'],
                'phone' => $transaction['phone'],
                'address' => $transaction['address']
            ];
        }
        $response = [
            'status' => 'success',
            'data' => [
                'receipt_no' => $transaction['receipt_no'],
                'sale_date' => $transaction['sale_date'],
                'items' => $items,
                'total' => $transaction['total'],
                'discount' => $transaction['discount'],
                'amount_paid' => $transaction['amount_paid'],
                'payment_method' => $transaction['payment_method'],
                'customer_info' => $customer_info
            ]
        ];
        return_json($response);
        $stmt_items->close();
    } else {
        return_json([
            'status' => 'error',
            'message' => 'Transaction not found'
        ]);
    }
    $stmt->close();
}

// GET SUPPLIERS
elseif ($_SERVER['REQUEST_METHOD'] === 'GET' && isset($_GET['action']) && $_GET['action'] == 'get_suppliers') {
    $sql = "SELECT id, supplier_name FROM suppliers ORDER BY supplier_name";
    $result = $conn->query($sql);
    $suppliers = [];
    while ($row = $result->fetch_assoc()) {
        $suppliers[] = $row;
    }
    return_json([
        'status' => 'success',
        'data' => $suppliers
    ]);
}

// RESTOCK PRODUCT
elseif ($_SERVER['REQUEST_METHOD'] === 'POST' && isset($data['action']) && $data['action'] == 'restock_product') {
    $required_fields = ['item_id', 'quantity', 'supplier_id', 'cashier_id'];
    foreach ($required_fields as $field) {
        if (!isset($data[$field])) {
            return_json(['status' => 'error', 'message' => "$field is required"]);
        }
    }
    $item_id = (int)$data['item_id'];
    $quantity = (int)$data['quantity'];
    $supplier_id = (int)$data['supplier_id'];
    $cashier_id = $conn->real_escape_string($data['cashier_id']);
    $price_cost = isset($data['price_cost']) ? (float)$data['price_cost'] : 0;
    $invoice_no = isset($data['invoice_no']) ? $conn->real_escape_string($data['invoice_no']) : '';
    $notes = isset($data['notes']) ? $conn->real_escape_string($data['notes']) : '';
    $user_id = isset($data['user_id']) ? (int)$data['user_id'] : 1;
    $conn->begin_transaction();
    try {
        $sql = "INSERT INTO supplier_prices (
                  item_id, supplier_id, stock_per_unit, 
                  supplier_price_unit, price_cost,
                  invoice_no, notes, date_keyin, user_id, cashier_id, synced
               ) VALUES (?, ?, ?, ?, ?, ?, ?, NOW(), ?, ?, 0)";
        $stmt = $conn->prepare($sql);
        $stmt->bind_param("iiiddssis", $item_id, $supplier_id, $quantity, $price_cost, $price_cost, $invoice_no, $notes, $user_id, $cashier_id);
        $stmt->execute();
        $stmt->close();
        $sql = "INSERT INTO stock_history (
                  item_id, supplier_id, quantity,
                  price_cost, invoice_no, notes,
                  user_id, created_at, synced
               ) VALUES (?, ?, ?, ?, ?, ?, ?, NOW(), 0)";
        $stmt = $conn->prepare($sql);
        if (!$stmt) {
            throw new Exception("Prepare failed for stock_history: " . $conn->error);
        }
        $stmt->bind_param("iiidssi", $item_id, $supplier_id, $quantity, $price_cost, $invoice_no, $notes, $user_id);
        $stmt->execute();
        $stmt->close();
        $stock_sql = "SELECT COALESCE(SUM(stock_per_unit), 0) as stock 
                      FROM supplier_prices 
                      WHERE item_id = ?";
        $stmt = $conn->prepare($stock_sql);
        if (!$stmt) {
            throw new Exception("Prepare failed for stock query: " . $conn->error);
        }
        $stmt->bind_param("i", $item_id);
        $stmt->execute();
        $stock = $stmt->get_result()->fetch_assoc();
        $stmt->close();
        $conn->commit();
        return_json([
            'status' => 'success',
            'message' => 'Product restocked successfully',
            'data' => [
                'item_id' => $item_id,
                'quantity_added' => $quantity,
                'new_stock' => (int)$stock['stock'],
                'supplier_id' => $supplier_id
            ]
        ]);
    } catch (Exception $e) {
        $conn->rollback();
        return_json([
            'status' => 'error',
            'message' => 'Restock failed: ' . $e->getMessage()
        ]);
        error_log("Restock product error: " . $e->getMessage());
    }
}

// GET PRODUCT DETAILS
elseif ($_SERVER['REQUEST_METHOD'] === 'GET' && isset($_GET['action']) && $_GET['action'] == 'get_product_details' && isset($_GET['barcode'])) {
    $barcode = trim($_GET['barcode']);
    $debug = "Fetching details for barcode: $barcode\n";
    if (!$conn) {
        $debug .= "Database connection failed: No valid connection\n";
        return_json(['status' => 'error', 'message' => 'Database connection failed', 'debug' => $debug]);
    }
    $sql = "SELECT i.id, i.item_name, COALESCE(sp.unit_per_pack, 1) as unit_per_pack, COALESCE(sp.pack_per_box, 1) as pack_per_box
            FROM items i
            LEFT JOIN supplier_prices sp ON sp.item_id = i.id AND sp.date_keyin = (
                SELECT MAX(date_keyin) FROM supplier_prices sp2 WHERE sp2.item_id = i.id
            )
            WHERE ? IN (i.barcode_per_unit, i.barcode_per_pack, i.barcode_per_box)
            LIMIT 1";
    $stmt = $conn->prepare($sql);
    if (!$stmt) {
        $debug .= "Prepare failed: " . $conn->error . "\n";
        return_json(['status' => 'error', 'message' => 'Prepare failed: ' . $conn->error, 'debug' => $debug]);
    }
    $stmt->bind_param("s", $barcode);
    $stmt->execute();
    $result = $stmt->get_result();
    $product = $result->fetch_assoc();
    if ($product) {
        $debug .= "Found details: " . print_r($product, true) . "\n";
        return_json([
            'status' => 'success',
            'data' => [
                'id' => $product['id'],
                'name' => $product['item_name'],
                'unit_per_pack' => $product['unit_per_pack'],
                'pack_per_box' => $product['pack_per_box']
            ],
            'debug' => $debug
        ]);
    } else {
        $debug .= "No details found for barcode: $barcode. Checking items: ";
        $checkSql = "SELECT id, item_name FROM items WHERE ? IN (barcode_per_unit, barcode_per_pack, barcode_per_box)";
        $checkStmt = $conn->prepare($checkSql);
        $checkStmt->bind_param("s", $barcode);
        $checkStmt->execute();
        $checkResult = $checkStmt->get_result();
        $checkProduct = $checkResult->fetch_assoc();
        $debug .= print_r($checkProduct, true) . "\n";
        return_json(['status' => 'error', 'message' => 'Product details not found', 'debug' => $debug]);
    }
    $stmt->close();
}

// GET PRODUCT BY NAME
elseif ($_SERVER['REQUEST_METHOD'] === 'GET' && isset($_GET['action']) && $_GET['action'] == 'get_product_by_name' && isset($_GET['name'])) {
    $name = $conn->real_escape_string($_GET['name']);
    $sql = "SELECT 
               i.id, 
               i.item_name as name,
               i.barcode_per_unit as barcode,
               (SELECT sp.supplier_price_unit 
                FROM supplier_prices sp 
                WHERE sp.item_id = i.id 
                ORDER BY sp.date_keyin DESC 
                LIMIT 1) as price,
               (COALESCE(SUM(sp.stock_per_unit), 0) - 
               COALESCE((SELECT SUM(si.quantity) 
                        FROM sales_items si
                        JOIN sales s ON si.sale_id = s.id
                        WHERE si.item_id = i.id), 0)) as stock
            FROM items i
            LEFT JOIN supplier_prices sp ON i.id = sp.item_id
            WHERE i.item_name = ?
            GROUP BY i.id
            LIMIT 1";
    $stmt = $conn->prepare($sql);
    if (!$stmt) {
        return_json(['status' => 'error', 'message' => 'Prepare failed: ' . $conn->error]);
    }
    $stmt->bind_param("s", $name);
    $stmt->execute();
    $result = $stmt->get_result();
    if ($result->num_rows > 0) {
        $product = $result->fetch_assoc();
        return_json([
            'status' => 'success',
            'data' => [
                'id' => $product['id'],
                'name' => $product['name'],
                'barcode' => $product['barcode'],
                'price' => $product['price'],
                'stock' => (int)$product['stock']
            ]
        ]);
    } else {
        return_json([
            'status' => 'error',
            'message' => 'Product not found'
        ]);
    }
    $stmt->close();
}

// GET PRODUCT FOR RESTOCK
elseif ($_SERVER['REQUEST_METHOD'] === 'GET' && isset($_GET['action']) && $_GET['action'] == 'get_product_for_restock' && isset($_GET['item_id'])) {
    $item_id = (int)$_GET['item_id'];
    $product_sql = "SELECT id, item_name, barcode_per_unit FROM items WHERE id = ?";
    $stmt = $conn->prepare($product_sql);
    if (!$stmt) {
        return_json(['status' => 'error', 'message' => 'Prepare failed: ' . $conn->error]);
    }
    $stmt->bind_param("i", $item_id);
    $stmt->execute();
    $product = $stmt->get_result()->fetch_assoc();
    $stmt->close();
    if (!$product) {
        return_json(['status' => 'error', 'message' => 'Product not found']);
    }
    $stock_sql = "SELECT COALESCE(SUM(stock_per_unit), 0) as stock 
                  FROM supplier_prices 
                  WHERE item_id = ?";
    $stmt = $conn->prepare($stock_sql);
    if (!$stmt) {
        return_json(['status' => 'error', 'message' => 'Prepare failed: ' . $conn->error]);
    }
    $stmt->bind_param("i", $item_id);
    $stmt->execute();
    $stock = $stmt->get_result()->fetch_assoc();
    $stmt->close();
    $suppliers_sql = "SELECT s.id, s.supplier_name 
                     FROM suppliers s
                     ORDER BY s.supplier_name";
    $stmt = $conn->prepare($suppliers_sql);
    if (!$stmt) {
        return_json(['status' => 'error', 'message' => 'Prepare failed: ' . $conn->error]);
    }
    $stmt->execute();
    $suppliers = $stmt->get_result()->fetch_all(MYSQLI_ASSOC);
    $stmt->close();
    $price_sql = "SELECT 
                     sp.supplier_price_unit, 
                     sp.price_cost,
                     sp.invoice_no
                  FROM supplier_prices sp
                  WHERE sp.item_id = ? 
                  ORDER BY sp.date_keyin DESC 
                  LIMIT 1";
    $stmt = $conn->prepare($price_sql);
    if (!$stmt) {
        return_json(['status' => 'error', 'message' => 'Prepare failed: ' . $conn->error]);
    }
    $stmt->bind_param("i", $item_id);
    $stmt->execute();
    $price = $stmt->get_result()->fetch_assoc();
    $stmt->close();
    return_json([
        'status' => 'success',
        'data' => [
            'product' => $product,
            'stock' => (int)$stock['stock'],
            'suppliers' => $suppliers,
            'last_price' => $price ? [
                'supplier_price_unit' => $price['supplier_price_unit'],
                'price_cost' => $price['price_cost'],
                'invoice_no' => $price['invoice_no']
            ] : null
        ]
    ]);
}

// GET STORE INFO
elseif ($_SERVER['REQUEST_METHOD'] === 'GET' && isset($_GET['action']) && $_GET['action'] == 'get_store_info') {
    $sql = "SELECT * FROM store_settings LIMIT 1";
    $result = $conn->query($sql);
    if ($result->num_rows > 0) {
        return_json($result->fetch_assoc());
    } else {
        return_json(['status' => 'error', 'message' => 'Store info not found']);
    }
}

// DEFAULT ERROR
else {
    return_json(['status' => 'error', 'message' => 'Invalid request or action']);
    error_log("Invalid request: " . $_SERVER['REQUEST_METHOD'] . " " . $_SERVER['REQUEST_URI']);
}

$conn->close();
?>
