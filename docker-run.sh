#!/usr/bin/env bash
set -e

SCENARIO="${1:-recovery_scenario}"

echo "=== 启动 Open vSwitch ==="
mkdir -p /var/run/openvswitch /var/log/openvswitch
ovsdb-tool create /etc/openvswitch/conf.db /usr/share/openvswitch/vswitch.ovsschema 2>/dev/null || true
ovsdb-server --remote=punix:/var/run/openvswitch/db.sock \
    --remote=db:Open_vSwitch,Open_vSwitch,manager_options \
    --pidfile --detach --log-file
ovs-vsctl --no-wait init
ovs-vswitchd --pidfile --detach --log-file
echo "OVS 启动完成"
ovs-vsctl show

echo ""
echo "=== 启动 Ryu 控制器 ==="
FORWARDING_APP="${RYU_FORWARDING_APP:-src.controller.topology_aware_switch}"
PYTHONPATH="${RYU_PYTHONPATH:-$PWD}" ryu-manager --observe-links \
    "$FORWARDING_APP" \
    ryu.app.ofctl_rest \
    ryu.app.rest_topology \
    --wsapi-port 8080 \
    > /tmp/ryu.log 2>&1 &
RYU_PID=$!

echo "等待 Ryu 就绪（REST:8080 + OpenFlow:6633）..."
RYU_READY=0
for i in $(seq 1 30); do
    REST_OK=0
    OF_OK=0
    python3 -m src.controller.ryu_probe --base-url http://127.0.0.1:8080 2>/dev/null && REST_OK=1
    python3 -c "import socket; s=socket.socket(); s.settimeout(1); s.connect(('127.0.0.1',6633)); s.close()" 2>/dev/null && OF_OK=1
    if [ $REST_OK -eq 1 ] && [ $OF_OK -eq 1 ]; then
        echo "Ryu 已就绪 (REST + OpenFlow)"
        RYU_READY=1
        break
    fi
    sleep 1
    echo "  等待中... ($i/30) REST=$REST_OK OF=$OF_OK"
done

if [ $RYU_READY -eq 0 ]; then
    echo ""
    echo "!!! Ryu 启动失败，日志如下 ==="
    cat /tmp/ryu.log
    exit 1
fi

echo ""
echo "--- Ryu 启动日志（最后10行）---"
tail -10 /tmp/ryu.log
echo "--------------------------------"
echo ""

echo "=== 运行实验场景: $SCENARIO ==="
MININET_USE_TC=false python3 -m src.twin.experiment_runner \
    --scenario "$SCENARIO" \
    --output-csv "data/exports/${SCENARIO}.csv"

echo ""
echo "=== 生成图表 ==="
bash scripts/plot_results.sh

echo ""
echo "=== 完成！结果文件 ==="
ls -la data/exports/
ls -la data/plots/

kill $RYU_PID 2>/dev/null || true
