import { createBottomTabNavigator } from "@react-navigation/bottom-tabs";
import { NavigationContainer } from "@react-navigation/native";
import { createNativeStackNavigator } from "@react-navigation/native-stack";
import React, { useState } from "react";
import { StyleSheet, Text, View } from "react-native";
import { SafeAreaProvider } from "react-native-safe-area-context";
import { StatusBar } from "expo-status-bar";

import { ScanResponse } from "./api/client";
import CaptureScreen from "./screens/CaptureScreen";
import LibraryScreen from "./screens/LibraryScreen";
import ReviewScreen from "./screens/ReviewScreen";
import { theme } from "./theme";

export type RootStackParamList = {
  Tabs: undefined;
  Review: undefined;
};

export type TabParamList = {
  Scan: undefined;
  Library: undefined;
};

const Stack = createNativeStackNavigator<RootStackParamList>();
const Tab = createBottomTabNavigator<TabParamList>();

function TabIcon({ label, focused }: { label: string; focused: boolean }) {
  const icons: Record<string, string> = { Scan: "📷", Library: "📚" };
  return (
    <View style={styles.tabIconWrap}>
      <Text style={[styles.tabIcon, focused && styles.tabIconFocused]}>{icons[label] ?? "•"}</Text>
      <Text style={[styles.tabLabel, focused && styles.tabLabelFocused]}>{label}</Text>
    </View>
  );
}

function MainTabs({
  onScanComplete,
}: {
  onScanComplete: (result: ScanResponse) => void;
}) {
  return (
    <Tab.Navigator
      screenOptions={({ route }) => ({
        headerShown: false,
        tabBarShowLabel: false,
        tabBarStyle: styles.tabBar,
        tabBarIcon: ({ focused }) => <TabIcon label={route.name} focused={focused} />,
      })}
    >
      <Tab.Screen name="Scan">
        {() => <CaptureScreen onScanComplete={onScanComplete} />}
      </Tab.Screen>
      <Tab.Screen name="Library" component={LibraryScreen} />
    </Tab.Navigator>
  );
}

export default function App() {
  const [scanResult, setScanResult] = useState<ScanResponse | null>(null);

  return (
    <SafeAreaProvider>
      <NavigationContainer>
        <StatusBar style="dark" />
        <Stack.Navigator>
          <Stack.Screen name="Tabs" options={{ headerShown: false }}>
            {(props) => (
              <MainTabs
                onScanComplete={(result) => {
                  setScanResult(result);
                  props.navigation.navigate("Review");
                }}
              />
            )}
          </Stack.Screen>
          <Stack.Screen
            name="Review"
            options={{
              title: "Review matches",
              headerStyle: { backgroundColor: theme.colors.bg },
              headerTintColor: theme.colors.primary,
              headerTitleStyle: { fontWeight: "700" },
            }}
          >
            {(props) => (
              <ReviewScreen
                scanResult={scanResult}
                onSaved={() => props.navigation.navigate("Tabs", { screen: "Library" })}
                onBack={() => props.navigation.goBack()}
              />
            )}
          </Stack.Screen>
        </Stack.Navigator>
      </NavigationContainer>
    </SafeAreaProvider>
  );
}

const styles = StyleSheet.create({
  tabBar: {
    height: 78,
    paddingTop: 8,
    paddingBottom: 12,
    backgroundColor: theme.colors.surface,
    borderTopColor: theme.colors.border,
    borderTopWidth: 1,
  },
  tabIconWrap: { alignItems: "center", gap: 4 },
  tabIcon: { fontSize: 22, opacity: 0.55 },
  tabIconFocused: { opacity: 1 },
  tabLabel: { fontSize: 12, color: theme.colors.textMuted, fontWeight: "600" },
  tabLabelFocused: { color: theme.colors.primary },
});
